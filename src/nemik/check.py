# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik-check: validate every workstream's queue against nemik's SHACL shapes.

Exit 0 when every queue under the root translates with no sh:Violation; exit 1 otherwise.
Every run first prints `provenance:` lines: nemik's own commit (with `+uncommitted` when its
tree is dirty), and per queue `committed`, `uncommitted` or `untracked-source`. The exit code
means only the verdict.
sh:Warning results (vocabulary divergence not yet agreed across repos, stale edges into residue)
are printed but do not fail the check: divergence is reported to summit's floor, not enforced. This is the check summit registers the capability against.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import tomllib
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path

from mikemol.pathsforward.store import UnreadableStateError
from rdflib import Graph, Literal

from nemik import cachestore, warrantdebt
from nemik.adapter import (
    BASE,
    NEMIK,
    OSLC_CM,
    bind,
    queue_graph,
    tick_notes,
    waypoint_uri,
    workstream_uri,
)
from nemik.adoption import adoption
from nemik.blocks import (
    annotate,
    lowered_ratchet,
    over_ratchet,
    ref,
    unmanifested_by_repo,
)
from nemik.collapse import collapse as umbrellas_of
from nemik.collapse import disagreements
from nemik.collapse import lines as collapse_lines
from nemik.digest import collapse
from nemik.idle import findings as idle_findings
from nemik.rolls import idle_run, stalled
from nemik.workrows import NO_BOUND, ready_stamps, small_done_stamps, upper_quantile

QUEUE, LEDGER = "paths-forward.json", "paths-forward.ledger"
WRITER = "mikemol-paths-forward --state"
STALL_RUN = 2
NEITHER_QUANTILE = 0.9  # the share of small cards that finished within the bound
NEITHER_SAMPLES = 10  # fewer finished small cards than this and no bound is learned
SECONDS_A_DAY = 86400


def seconds_between(earlier: str, later: str) -> float | None:
    """Give the seconds from one ISO stamp to another.

    Args:
        earlier: The earlier stamp.
        later: The later stamp.

    Returns:
        The difference, or None when either is not an ISO time.

    """
    try:
        return (
            dt.datetime.fromisoformat(later) - dt.datetime.fromisoformat(earlier)
        ).total_seconds()
    except ValueError:
        return None


def ready_neither(
    root: Path, now: str
) -> tuple[float, dict[str, list[tuple[float, str]]]]:
    """nemik:W489: the ready cards left untouched past how long small cards take to finish.

    The bound is learned, not typed: the 90th percentile of the time from issue to completion of
    the done cards declared small, across every queue. A ready card whose last touch (issue or
    work) is older than that is neither being done nor atomized. No bound is learned from fewer
    than ten finished small cards.

    Args:
        root: The fleet root.
        now: The instant to age the cards against, as an ISO stamp.

    Returns:
        (the bound in seconds, or NO_BOUND; per repo the late cards as (age in seconds, symbol),
        oldest first).

    """
    texts = {
        repo: path.read_text(encoding="utf-8")
        for repo, path in workstream_files(root, QUEUE)
    }
    spans = [
        span
        for text in texts.values()
        for issued, completed in small_done_stamps(text)
        if (span := seconds_between(issued, completed)) is not None and span >= 0
    ]
    bound = (
        upper_quantile(spans, NEITHER_QUANTILE)
        if len(spans) >= NEITHER_SAMPLES
        else NO_BOUND
    )
    late: dict[str, list[tuple[float, str]]] = {}
    for repo, text in texts.items():
        for symbol, touched in ready_stamps(text):
            age = seconds_between(touched, now)
            if bound >= 0 and age is not None and age > bound:
                late.setdefault(repo, []).append((age, symbol))
    return bound, {repo: sorted(rows, reverse=True) for repo, rows in late.items()}


def add_ready_neither_infos(root: Path, by_repo: dict[str, list[Finding]]) -> None:
    """nemik:W489: one Info per repo counting its ready cards left untouched past the bound.

    One row per repo, not per card (the hook prints every row into every session); `nemik-check
    --ready-neither` lists the cards.

    Args:
        root: The fleet root.
        by_repo: The findings per repo, added to in place.

    """
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    bound, late = ready_neither(root, now)
    for repo, rows in sorted(late.items()):
        age, symbol = rows[0]
        found = (
            f"{len(rows)} ready cards untouched for longer than {bound / SECONDS_A_DAY:.1f} d, "
            f"how long 9 in 10 small cards took to finish (oldest {symbol}, "
            f"{age / SECONDS_A_DAY:.1f} d): do each or atomize it"
        )
        by_repo.setdefault(repo, []).append(("Info", "--", found))


def add_umbrella_infos(merged: Graph, by_repo: dict[str, list[Finding]]) -> None:
    """nemik:W710: tell each repo how many blocked cards wait behind one of its cards.

    nemik.collapse rolls blocked cards up under the node that dominates them. One Info per repo
    (the fleet has over a hundred umbrellas, and every session's hook prints every row) names how
    many umbrellas sit under that repo's cards, how many blocked cards they hold, and the largest.

    Args:
        merged: The merged queue graph.
        by_repo: The findings per repo, added to in place.

    """
    held: dict[str, list[tuple[int, str]]] = {}
    for _, blockers, _, members in umbrellas_of(blocked_rows(merged)):
        held.setdefault(blockers[0].partition(":")[0], []).append(
            (len(members), blockers[0])
        )
    for repo, found in sorted(held.items()):
        size, card = max(found)
        found_text = (
            f"{len(found)} umbrella(s) hold {sum(n for n, _ in found)} blocked cards; the "
            f"largest is {card} with {size} cards waiting behind it: nemik-collapse lists them"
        )
        by_repo.setdefault(repo, []).append(("Info", "--", found_text))


def add_roll_warnings(
    root: Path, merged: Graph, by_repo: dict[str, list[Finding]]
) -> None:
    """nemik:W683: warn on a repo whose last tick rolls all advanced nothing while cards are ready.

    mikemol-paths-forward --tick-roll ends its ledger note with `[rolled; advanced N]` (mtools:
    W1589). A run of rolls at advanced 0 beside ready cards is a session that keeps rolling
    without landing, which the roll would otherwise hide.

    Args:
        root: The directory holding the repos.
        merged: The merged queue graph.
        by_repo: The findings per repo, added to in place.

    """
    ready: dict[str, int] = {}
    for node in merged.subjects(OSLC_CM.state, NEMIK.Ready):
        repo = ref(node).partition(":")[0]
        ready[repo] = ready.get(repo, 0) + 1
    for repo, path in workstream_files(root, LEDGER):
        notes = tick_notes(path)
        if stalled(notes, ready.get(repo, 0), STALL_RUN):
            found = (
                f"the last {idle_run(notes)} tick rolls advanced 0 while "
                f"{ready.get(repo, 0)} cards are ready: the session rolls without landing; "
                "work a ready card, or block it on what it waits for"
            )
            by_repo.setdefault(repo, []).append(("Warning", "--", found))


def collapse_main(argv: list[str] | None = None) -> None:
    """nemik:W711: print the fleet's collapse umbrellas and the enables edges that escape them.

    Reads every queue without validating it (survey(check=False)), builds each open card's
    (waits, enables) row and prints nemik.collapse.lines. `--root DIR` names the fleet root.
    Nothing is applied.

    Args:
        argv: The arguments after the program name, or None for sys.argv.

    """
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[args.index("--root") + 1]) if "--root" in args else default_root()
    whole = bind(Graph())
    for _, g, _ in survey(root, check=False):
        if g is not None:
            whole += g
    sys.stdout.write("\n".join(collapse_lines(blocked_rows(whole))) + "\n")


def manifest_ratchet() -> dict[str, int]:
    """nemik:W685: how many ready cards without a manifest each repo is declared to have.

    Measured, never typed as a cap: the [manifest_ratchet] table of rank-weights.toml (the file
    that already holds the other declared thresholds) holds each repo's count as
    `nemik-check --unmanifested` printed it, and it only falls.

    Returns:
        repo -> the count the ratchet allows; empty when the table is absent.

    """
    text = files("nemik.data").joinpath("rank-weights.toml").read_text(encoding="utf-8")
    document: dict[str, object] = tomllib.loads(text)
    table = document.get("manifest_ratchet")
    if not isinstance(table, dict):
        return {}
    return {str(repo): int(n) for repo, n in table.items()}


def manifest_findings(merged: Graph, declared: dict[str, int]) -> dict[str, str]:
    """nemik:W685: the repos whose ready cards without a manifest passed the ratchet.

    A ready card with no manifest looks pickable in the view and cannot be stacked, so a repo that
    lets the count grow past what was measured is told, as a Warning on the repo.

    Args:
        merged: The merged queue graph.
        declared: The ratchet, repo -> the count it allows.

    Returns:
        The warning text per repo over its ratchet.

    """
    over = over_ratchet(unmanifested_by_repo(merged), declared)
    return {
        repo: f"{n} ready cards have no manifest, over the {allowed} the ratchet allows: give each "
        "a manifest and size (--manifest ... --size ...) or block it on what it waits for"
        for repo, (n, allowed) in over.items()
    }


def add_manifest_warnings(merged: Graph, by_repo: dict[str, list[Finding]]) -> None:
    """nemik:W685: append each over-ratchet repo's Warning to its findings.

    Args:
        merged: The merged queue graph.
        by_repo: The findings per repo, added to in place.

    """
    for repo, found in sorted(manifest_findings(merged, manifest_ratchet()).items()):
        by_repo.setdefault(repo, []).append(("Warning", "--", found))


def ready_neither_report(root: Path, repo: str | None) -> int:
    """nemik:W489: list the ready cards untouched past the learned bound, oldest first.

    Args:
        root: The directory holding the repos.
        repo: The one repo to list, or None for all.

    Returns:
        0.

    """
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    bound, late = ready_neither(root, now)
    if bound < 0:
        sys.stdout.write("no bound learned: fewer than ten finished small cards\n")
        return 0
    sys.stdout.write(
        f"bound: {bound / SECONDS_A_DAY:.1f} d (p90 of finished small cards)\n"
    )
    for name, rows in sorted(late.items()):
        if repo is not None and name != repo:
            continue
        sys.stdout.write(f"{name}: {len(rows)} ready cards untouched past the bound\n")
        sys.stdout.writelines(
            f"  {name}:{symbol}  {age / SECONDS_A_DAY:.1f} d\n" for age, symbol in rows
        )
    return 0


def report_mode(report: str | None, root: Path, repo: str | None) -> int | None:
    """nemik:W693, W685, W489: run the one report mode the arguments ask for, if any.

    Args:
        report: "integrity", "unmanifested", "ready-neither", or None for none.
        root: The directory holding the repos.
        repo: The one repo to report on, or None for all.

    Returns:
        The report's exit status, or None when no report mode was asked for.

    """
    if report == "integrity":
        return integrity_report(root, repo)
    if report == "unmanifested":
        return unmanifested_report(root)
    if report == "ready-neither":
        return ready_neither_report(root, repo)
    return None


def unmanifested_report(root: Path) -> int:
    """Print the ratchet as it should stand now: each repo's count, never above the declared one.

    Args:
        root: The directory holding the repos.

    Returns:
        0.

    """
    whole = bind(Graph())
    for _, g, _ in survey(root, check=False):
        if g is not None:
            whole += g
    lowered = lowered_ratchet(unmanifested_by_repo(whole), manifest_ratchet())
    sys.stdout.write(json.dumps(lowered, indent=1) + "\n")
    return 0


def blocked_rows(merged: Graph) -> dict[str, tuple[list[str], list[str]]]:
    """nemik:W693: every open card with the cards it waits on and the cards it enables.

    Args:
        merged: The merged queue graph.

    Returns:
        card -> (waits, enables), as `repo:W<n>` references, over open cards only.

    """
    open_cards = {
        n
        for n in merged.subjects(OSLC_CM.state, None)
        if (n, OSLC_CM.state, NEMIK.Done) not in merged
    }
    return {
        ref(n): (
            sorted(
                {ref(t) for t in merged.objects(n, NEMIK.waitsFor) if t in open_cards}
            ),
            sorted(
                {ref(t) for t in merged.objects(n, NEMIK.enables) if t in open_cards}
            ),
        )
        for n in open_cards
    }


def integrity_commands(merged: Graph, root: Path) -> dict[str, list[str]]:
    """nemik:W693: for each integrity finding, the two ways to fix it, as commands (a dry run).

    A card that enables E says E cannot proceed without it, but where E does not wait on the card
    the enables and blocked_on edges disagree. Either E should wait on the card (add the
    blocked_on) or the card should not enable E (drop the enables edge). Which is right is the
    owning repo's call, so both are printed and nothing is applied.

    Args:
        merged: The merged queue graph.
        root: The directory holding the repos, for the state-file paths in the commands.

    Returns:
        The lines to print, by the repo that holds the card.

    """
    rows = blocked_rows(merged)
    out: dict[str, list[str]] = {}
    # nemik:W742: the state file of each repo as the fleet reader finds it, so the host repo
    # (github) prints its own queue at the root and not a directory that does not exist
    queues = dict(workstream_files(root, QUEUE))

    def state_of(repo: str) -> str:
        return f"{WRITER} {queues.get(repo, root / repo / '.claude' / QUEUE)}"

    for card, escaped in disagreements(rows):
        repo, _, sym = card.partition(":")
        erepo, _, esym = escaped.partition(":")
        keep = [r.removeprefix(f"{repo}:") for r in rows[card][1] if r != escaped]
        waiting = sorted(
            str(w) for w in merged.objects(waypoint_uri(erepo, esym), NEMIK.blockedOn)
        )
        drop = f"{state_of(repo)} --update {sym} --enables {' '.join(keep)}".rstrip()
        wait = " ".join([*waiting, sym if erepo == repo else card])
        add = f"{state_of(erepo)} --update {esym} --blocked-on {wait} --blocked-kind agent"
        out.setdefault(repo, []).extend(
            [
                f"{card}: enables {escaped}, which does not wait on it",
                f"    drop the enables edge: {drop}",
                f"    or add the blocked_on: {add}",
            ]
        )
    return out


def integrity_findings(merged: Graph) -> dict[str, list[tuple[str, str]]]:
    """nemik:W693: the enables edges whose target does not wait on the card that enables it.

    The operator (2026-10-18, 695f3e0a line 80516) called an enables edge into a card that is not
    transitively blocked behind its source a data-integrity problem: the enables and blocked_on
    edges disagree. A card that also has other blockers (a join) still waits on this one and is
    not named. This names each such edge so it is fixed where it is written.

    Args:
        merged: The merged queue graph.

    Returns:
        (symbol, message) pairs by repo, for each open card whose enables names a card that does
        not wait on it.

    """
    found: dict[str, list[tuple[str, str]]] = {}
    for card, escaped in disagreements(blocked_rows(merged)):
        repo, _, symbol = card.partition(":")
        said = (
            f"enables {escaped}, which does not wait on it: the enables and blocked_on edges "
            "disagree (add the blocked_on, or drop the enables edge)"
        )
        found.setdefault(repo, []).append((symbol, said))
    return found


def default_root() -> Path:
    """$NEMIK_ROOT, else ~/github."""
    return Path(os.environ.get("NEMIK_ROOT") or Path.home() / "github")


def workstream_files(root: Path, name: str) -> list[tuple[str, Path]]:
    """(repo, path) for `name` under either layout, keyed by repo.

    ~/github layout: <root>/<repo>/.claude/<name>. Export layout (luthen's host-side copy, which
    carries only these two files per repo): <root>/<repo>/<name>.
    """
    found = {p.parents[1].name: p for p in root.glob(f"*/.claude/{name}")}
    found |= {
        p.parent.name: p for p in root.glob(f"*/{name}") if p.parent.name != ".claude"
    }
    own = root / ".claude" / name
    if own.exists():
        # nemik:W224: a root with a queue of its own is a workstream too, named by its directory,
        # beside the workstreams it contains (the host queue at ~/github/.claude over every repo,
        # cited `github:W<n>`); a root that holds no repos (--root pointed at one repo) is the
        # same rule with nothing beneath it. A child of the same name wins. Resolved: `--root .`
        # has the name '' (nemik:W142), which left the workstream unnamed and its own
        # <repo>:W<n> references unresolvable.
        found.setdefault(root.resolve().name, own)
    # A dot-named directory (e.g. .linux-sources-gate-wt, a git worktree of linux-sources) carries
    # another workstream's queue at another commit, not a workstream of its own; it cannot be
    # cited either, since mtools' <repo>:W<n> requires the repo to start alphanumeric. Counting it
    # doubled every block it holds and left the copies unclaimable.
    return sorted((repo, p) for repo, p in found.items() if not repo.startswith("."))


def shapes() -> Graph:
    g = Graph()
    g.parse(
        data=files("nemik.data").joinpath("shapes.ttl").read_text(), format="turtle"
    )
    return g


Finding = tuple[str, str, str]  # (severity, focus symbol, message)


def unchecked(
    graphs: dict[str, Graph | None], refused: dict[str, str]
) -> Iterator[tuple[str, Graph | None, list[Finding]]]:
    """Yield each queue's graph with no findings, the refused ones marked Unreadable (nemik:W620).

    Args:
        graphs: Each repo's queue graph, or None when mtools refused the file.
        refused: The reason for each refused repo.

    Yields:
        (repo, graph, findings) as survey does, the findings empty for a graph.

    """
    for repo, g in graphs.items():
        yield repo, g, [] if g is not None else [("Unreadable", "--", refused[repo])]


def survey(
    root: Path, phases: dict[str, float] | None = None, *, check: bool = True
) -> Iterator[tuple[str, Graph | None, list[Finding]]]:
    """Yield (repo, graph, findings) per queue; graph is None when mtools refuses the file.

    Validation runs ONCE over the merged graph, so an `enables` edge into another workstream
    (`repo:W<n>`, legal since mtools 9236d5e) resolves against that workstream's waypoints.
    Each finding is attributed to the workstream of its focus node.

    nemik:W399: when `phases` is given, the CPU seconds of each phase (parse, annotate, shacl,
    fleet_checks) are written into it, so a caller can see which part of a rebuild dominates.

    nemik:W620: with `check` false the graphs are read and no finding is computed, which is most of
    the cost (SHACL and the fleet checks); for a caller that wants a family built from the graphs.
    """
    mark = [time.process_time()]

    def lap(name: str) -> None:
        now = time.process_time()
        if phases is not None:
            phases[name] = phases.get(name, 0.0) + now - mark[0]
        mark[0] = now

    queues = workstream_files(root, QUEUE)
    known = frozenset(repo for repo, _ in queues)
    graphs: dict[str, Graph | None] = {}
    refused: dict[str, str] = {}
    merged = Graph()
    for repo, state_path in queues:
        try:
            qg = queue_graph(repo, state_path, known)
            qg.add(
                (
                    workstream_uri(repo),
                    NEMIK.pathsforwardAdoption,
                    Literal(adoption(state_path)),
                )
            )
            graphs[repo] = qg
            merged += qg
        except UnreadableStateError as exc:
            graphs[repo], refused[repo] = None, str(exc)
    lap("parse")
    annotate(merged)
    lap("annotate")
    from nemik.hostapply import HOST_REF, load

    # nemik:W256: a cited host-apply row the export does not hold is an unresolved citation. Only the
    # file is read (no exporter subprocess), and no export at all leaves the citation as it was.
    try:
        export = load(root, run_exporter=False)
    except ValueError:
        export = None
    if export is not None:
        for node, cited in list(merged.subject_objects(NEMIK.blockedOn)):
            m = HOST_REF.fullmatch(str(cited).strip())
            if m and m[1] not in export.rows:
                merged.add((node, NEMIK.unresolvedBlocker, cited))
    if not check:
        yield from unchecked(graphs, refused)
        return
    from nemik.shaclinc import findings as shacl_findings

    # nemik:W400: a rebuild in the same process re-validates only the nodes its change touches.
    # nemik:W625: and a fresh process starts from the last reader's caches (142 s CPU cold, 11 s
    # warm), kept in the user's cache directory; only the real fleet root is kept, so a test's
    # temporary root does not grow it.
    kept = root.resolve() == default_root().resolve()
    if kept:
        cachestore.restore_user()
    results = shacl_findings(str(root.resolve()), merged, shapes())
    if kept:
        cachestore.persist_user()
    lap("shacl")
    by_repo: dict[str, list[Finding]] = {repo: [] for repo in graphs}
    for focus, sev, msg in sorted(results):
        repo, _, sym = str(focus).removeprefix(BASE).partition("/")
        by_repo.setdefault(repo, []).append(
            (str(sev).rsplit("#", 1)[-1], sym or "--", str(msg))
        )
    # nemik:W331: every card on a dependency cycle that the operator cannot break is a Warning, so
    # the cause is fixed where it is written (usually an umbrella that lists its children under
    # `enables` and is blocked_on them). nemik.critical classifies the cycles.
    from nemik.critical import cycles

    cause = (
        "none of them can become ready (an umbrella listing its children under "
        "enables while blocked_on them is the usual cause)"
    )
    # nemik:W484 (mtools:W1134's ring of three): name the ring in order, "a:W1 -> a:W2 -> a:W1",
    # as the fleet's shared walker finds it, rather than as an unordered set of members.
    from nemik.blocks import dependency_cycles

    rings = [[ref(n) for n in ring] for ring in dependency_cycles(merged)]
    for members, operator_can_break in cycles(merged):
        if operator_can_break:
            continue
        for member in members:
            mrepo, _, msym = member.partition(":")
            ring = next(
                (r for r in rings if member in r and set(r) <= set(members)), None
            )
            if ring:
                at = ring.index(member)
                turn = [*ring[at:], *ring[:at], member]
                found = f"on a dependency cycle {' -> '.join(turn)}: {cause}"
            else:
                others = ", ".join(m for m in members if m != member) or "itself"
                found = f"on a dependency cycle with {others}: {cause}"
            by_repo.setdefault(mrepo, []).append(("Warning", msym, found))
    # nemik:W348: a repo holding more needs-you asks than the declared cap has made the operator its
    # bottleneck (the doc's "paralyzed waiting on too many parallel operator answers"). One Warning
    # on the repo, with the count and the oldest ask, so the remedy (batch, withdraw, share) is local.
    from rdflib import URIRef
    from rdflib.namespace import DCTERMS

    from nemik.blocks import operator_asks

    weights_toml = files("nemik.data").joinpath("rank-weights.toml").read_text()
    cap = int(
        tomllib.loads(weights_toml).get("saturation", {}).get("needs_you_per_repo", 10)
    )
    owed: dict[str, list[str]] = {}
    for ask in operator_asks(merged):
        if ask["category"] == "needs-you":
            owed.setdefault(str(ask["ref"]).partition(":")[0], []).append(
                str(ask["ref"])
            )
    remedy = (
        "the operator is this repo's bottleneck; batch them into one ask, withdraw those another "
        "path answers, or cite a shared ask (same ask as <repo>:W<n>)"
    )
    for orepo, refs in sorted(owed.items()):
        if len(refs) <= cap:
            continue
        stamps = sorted(
            str(merged.value(URIRef(BASE + r.replace(":", "/")), DCTERMS.created) or "")
            for r in refs
        )
        oldest = next((s[:10] for s in stamps if s), "unknown")
        found = f"{len(refs)} needs-you operator asks are open (cap {cap}, oldest issued {oldest}): {remedy}"
        by_repo.setdefault(orepo, []).append(("Warning", "--", found))
    # nemik:W685: a repo whose ready cards without a manifest passed the declared ratchet.
    add_manifest_warnings(merged, by_repo)
    add_roll_warnings(root, merged, by_repo)
    add_umbrella_infos(merged, by_repo)
    add_ready_neither_infos(root, by_repo)
    # nemik:W356: an inter-workstream SLA. A card blocked on another repo's open card for longer than
    # the declared number of loop ticks is a Warning on the BLOCKER's card, since that repo can act.
    sla = int(tomllib.loads(weights_toml).get("sla", {}).get("cross_repo_ticks", 48))
    for waiter, _, target in merged.triples((None, NEMIK.waitsFor, None)):
        wcite, tcite = ref(waiter), ref(target)
        wrepo, trepo = wcite.partition(":")[0], tcite.partition(":")[0]
        if wrepo == trepo or (target, OSLC_CM.state, None) not in merged:
            continue
        if (target, OSLC_CM.state, NEMIK.Done) in merged:
            continue
        if (waiter, OSLC_CM.state, NEMIK.Blocked) not in merged:
            continue
        # a blocker that itself waits on the operator cannot act; W348 counts that load instead
        if str(merged.value(target, NEMIK.blockedKind) or "") == "human":
            continue
        ticks = int(str(merged.value(waiter, NEMIK.ticksBlocked) or 0))
        if ticks <= sla:
            continue
        late = (
            f"has kept {wcite} waiting {ticks} loop ticks (SLA {sla}): answer it, re-scope "
            f"it, or tell {wrepo} why it waits"
        )
        by_repo.setdefault(trepo, []).append(("Warning", tcite.partition(":")[2], late))
    # nemik:W577: a loop that ticks idle with nothing workable is told to disarm or name its wait.
    idle_said = idle_findings(root, merged, [repo for repo, _ in queues])
    for irepo, said in idle_said.items():
        by_repo.setdefault(irepo, []).append(("Warning", "--", said))
    # nemik:W616, W617: a working card that looks stalled, or whose progress is invisible. Imported
    # here because stalled reads history and history reads check: a module-level import is a cycle.
    from nemik import stalled

    for srepo, rows in stalled.findings(root, merged, int(time.time())).items():
        by_repo.setdefault(srepo, []).extend(
            ("Warning", sym, said) for sym, said in rows
        )
    # nemik:W608: the warrant debt may only fall: a repo above its ceiling is told to warrant.
    debts = warrantdebt.findings(merged, warrantdebt.baseline())
    for drepo, dtext in debts.items():
        by_repo.setdefault(drepo, []).append(("Warning", "--", dtext))
    # nemik:W693: an enables edge whose target does not wait on its source (the operator's
    # data-integrity rule, 695f3e0a line 80516): the enables and blocked_on edges disagree.
    # Staged at Info, as ManifestShape was: the first run found 274 across the fleet, and a
    # Warning is not cosmetic, so it rises on a declared ratchet from that count, not before.
    for irepo, rows in integrity_findings(merged).items():
        by_repo.setdefault(irepo, []).extend(("Info", sym, said) for sym, said in rows)
    # nemik:W405: a card waiting on another repo's card that has open prerequisites of its own (an
    # umbrella, or a card a peer has since atomized) gets the leaves to cite instead, with the exact
    # re-point command, so the fix is one command rather than a hand search (three hand re-points of
    # nemik:W392 in one day, W870 -> W872 -> W878). Info only: it never changes the verdict.
    from nemik.rank import successors

    open_nodes = {
        n
        for n in merged.subjects(OSLC_CM.state, None)
        if (n, OSLC_CM.state, NEMIK.Done) not in merged
    }
    prereqs: dict = {}
    for n in open_nodes:
        for s in successors(merged, n):
            if s in open_nodes and s != n:
                prereqs.setdefault(s, set()).add(n)

    # An umbrella is what the shape calls one: two or more open children enable it. Only umbrellas are
    # descended (their work IS their children); a single step that waits on something is still the
    # step you wait for, so the descent stops at the first non-umbrella.
    def umbrella(n) -> bool:
        return len(prereqs.get(n, ())) >= 2

    for waiter, _, target in merged.triples((None, NEMIK.waitsFor, None)):
        if not umbrella(target) or waiter not in open_nodes:
            continue
        wrepo, trepo = ref(waiter).partition(":")[0], ref(target).partition(":")[0]
        if wrepo == trepo:
            continue
        seen, todo, leaves = {target}, [target], set()
        while todo:
            for p in prereqs.get(todo.pop(), ()):
                if p in seen:
                    continue
                seen.add(p)
                if umbrella(p):
                    todo.append(p)
                else:
                    leaves.add(ref(p))
        if not leaves:
            continue
        wsym = ref(waiter).partition(":")[2]
        pf = f"mikemol-paths-forward --state {wrepo}/.claude/paths-forward.json"
        if len(leaves) == 1:
            (leaf,) = leaves
            # `--update=W<n>`: the same argument to argparse, and never read as a "repo W<n>" cite
            hint = f"waits on {ref(target)}, whose open step is {leaf}: {pf} --update={wsym} --blocked-on {leaf}"
        else:
            hint = (
                f"waits on {ref(target)}, whose open steps are {', '.join(sorted(leaves))}: "
                f"cite the one that unblocks you ({pf} --update={wsym} --blocked-on <one of them>)"
            )
        by_repo.setdefault(wrepo, []).append(("Info", wsym, hint))
    # nemik:W279: a letter a waypoint cites as evidence must exist (moved to inbox/archive counts).
    # The export layout carries no inbox, so a root without any inbox directory is not asked.
    if any(root.glob("*/inbox")):
        for node, _, cited in merged.triples((None, NEMIK.letter, None)):
            repo, _, sym = str(node).removeprefix(BASE).partition("/")
            rel = str(cited)
            path = root / (rel if "/inbox/" in rel else f"{repo}/{rel}")
            archived = path.parent / "archive" / path.name
            if not (path.exists() or archived.exists()):
                missing = (
                    f"cites the letter {rel}, which is not under the root: fix the path"
                )
                by_repo.setdefault(repo, []).append(("Warning", sym, missing))
    lap("fleet_checks")
    for repo, g in graphs.items():
        if g is None:
            yield repo, None, [("Unreadable", "--", refused[repo])]
        else:
            yield repo, g, sorted(by_repo[repo])


def _git(cwd: Path, *argv: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), *argv], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def exported_commit(queue_dir: Path) -> tuple[str, str] | None:
    """Read `commit.json` beside an exported queue (nemik:W7): {"sha": str, "dirty": bool}.

    luthen's nemik_export.py writes this so the pod can report real provenance instead of a
    blanket `untracked-source` for every repo (the export tree has no .git of its own to read).
    Returns (state, sha) or None if the file is absent, unreadable, or malformed -- callers then
    fall back to the untracked-source reading.
    """
    try:
        data = json.loads((queue_dir / "commit.json").read_text())
        sha = str(data["sha"])
        return ("uncommitted" if data["dirty"] else "committed", sha)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def provenance(root: Path) -> list[str]:
    """What this verdict rests on: nemik's own commit, and each queue's committed-or-not state.

    One line per fact, prefixed `provenance:`, so a reader can grep them. A queue outside any git
    tree (luthen's export) reads `untracked-source`, unless the exporter also wrote `commit.json`
    beside it (nemik:W7), in which case the real state and sha are reported, suffixed `@<sha>`.
    """
    here = Path(__file__).resolve().parent
    sha = _git(here, "rev-parse", "--short=12", "HEAD")
    dirty = _git(here, "status", "--porcelain", "--", ".")
    lines = [f"provenance: nemik {sha or 'unknown'}{' +uncommitted' if dirty else ''}"]
    for repo, path in workstream_files(root, QUEUE):
        top = _git(path.parent, "rev-parse", "--show-toplevel")
        if top is None:
            exported = exported_commit(path.parent)
            state = f"{exported[0]}@{exported[1]}" if exported else "untracked-source"
        else:
            changed = _git(
                path.parent,
                "status",
                "--porcelain",
                "--",
                str(path),
                str(path.with_name(LEDGER)),
            )
            state = "uncommitted" if changed else "committed"
        lines.append(f"provenance: queue {repo} {state}")
    return lines


def _realizability(root: Path) -> int:
    """Print every live waypoint's realizability coordinate and residue (nemik:W247).

    Exit 0 when every waypoint is runtime-valid, 1 when any carries residue, 2 when a queue could
    not be judged (no pinned opa, an unreadable queue): not checked never reads as clean.
    """
    from datetime import UTC, datetime

    from mikemol.pathsforward.lock import stamp
    from mikemol.pathsforward.opa_eval import OpaUnavailableError

    from nemik.marks import MARKS, policy_version, provenance, read
    from nemik.realize import rows, runtime_valid, verdicts

    now, residue, unjudged = stamp(datetime.now(UTC)), 0, 0
    version = policy_version()
    # nemik:W236: the clock is the policy's input, so the verdicts below are a function of it; say which.
    print(f"as_of {now}  policy {version[:12]}")
    for repo, path in workstream_files(root, QUEUE):
        try:
            found = verdicts(repo, path, root, now)
        except (OpaUnavailableError, UnreadableStateError) as exc:
            print(f"NOT JUDGED {repo}: {exc}")
            unjudged += 1
            continue
        # nemik:W234: the writer's persisted marks are read, not re-derived; a stale one is named.
        marks, unreadable = read(path.parent / MARKS)
        print(f"{repo}: {len(found)} waypoint(s), {unreadable} unreadable mark line(s)")
        for verdict in found:
            residue += not runtime_valid(verdict)
            symbol = str(verdict.get("ref")).rsplit(":", 1)[-1]
            source = provenance(marks.get(symbol), now, version)
            for line in rows(verdict, source):
                print(f"  {line}")
    return 2 if unjudged else int(residue > 0)


def committed_verdict(root: Path, named: set[str]) -> int:
    """Print the queue provenance lines and say whether a named repo's queue is not committed.

    Args:
        root: The directory holding the repos.
        named: The repos to hold to the verdict; none named means every repo.

    Returns:
        4 when any named repo is read from an uncommitted or untracked queue, otherwise 0.

    """
    lines = provenance(root)
    sys.stdout.write("".join(f"{line}\n" for line in lines))
    stale = [
        line
        for line in lines
        if line.startswith("provenance: queue ")
        and line.split()[3].split("@")[0] != "committed"
        and (not named or line.split()[2] in named)
    ]
    return 4 if stale else 0


def integrity_report(root: Path, only: str | None = None) -> int:
    """Print the integrity findings per repo with the fixes as commands, and apply nothing.

    Args:
        root: The directory holding the repos.
        only: A repo to report on; None reports every repo. Each repo's session works its own.

    Returns:
        0.

    """
    whole = bind(Graph())
    for _, g, _ in survey(root, check=False):
        if g is not None:
            whole += g
    for repo, said in sorted(integrity_commands(whole, root).items()):
        if only is None or only == repo:
            sys.stdout.write(f"{repo}: {len(said) // 3} finding(s)\n")
            sys.stdout.write("".join(f"{line}\n" for line in said))
    return 0


DIGEST_FILE = "fleet-survey.json"
# seconds: bounds what an input the key does not name can make stale
DIGEST_MAX_AGE = 600
CODE_SUFFIXES = frozenset({".py", ".ttl", ".toml", ".json"})


def survey_inputs(root: Path, *, digest: bool) -> list[bytes]:
    """Name what a fleet survey's answer rests on (nemik:W763).

    The answer is a function of nemik's own code and data, each queue file and its ledger, and the
    commits the history checks read; each is a part here, by content. A queue or ledger that cannot
    be read counts as empty, so a vanished file changes the key.

    Returns:
        The parts, for cachestore.content_key.

    """
    here = Path(__file__).resolve().parent
    parts = [b"digest" if digest else b"full"]
    parts.extend(
        path.read_bytes()
        for path in sorted(here.rglob("*"))
        if path.suffix in CODE_SUFFIXES and path.is_file()
    )
    for repo, state in workstream_files(root, QUEUE):
        parts.append(repo.encode())
        for kept in (state, state.with_name(LEDGER)):
            try:
                parts.append(kept.read_bytes())
            except OSError:
                parts.append(b"")
        parts.append((_git(state.parent, "rev-parse", "HEAD") or "").encode())
    return parts


def survey_lines(root: Path, *, digest: bool) -> tuple[list[str], int, Graph]:
    """Run the fleet survey and print-ready lines for it.

    Returns:
        (lines, how many queues violate or are unreadable, the merged graph).

    """
    lines: list[str] = []
    merged, failed = bind(Graph()), 0
    for repo, g, findings in survey(root):
        if g is None:
            lines.append(f"UNREADABLE {repo}: {findings[0][2]}")
            failed += 1
            continue
        violates = any(sev == "Violation" for sev, _, _ in findings)
        lines.append(f"{'VIOLATES  ' if violates else 'OK        '}{repo}")
        lines.extend(
            f"  {sev:9} {focus:6} {msg}"
            for sev, focus, msg in (collapse(findings) if digest else findings)
        )
        failed += violates
        merged += g
    return lines, failed, merged


def cached_survey(root: Path, *, digest: bool) -> tuple[list[str], int]:
    """Answer the fleet survey from the last run when none of its inputs changed (nemik:W763).

    Only the real fleet root is kept, as survey does for its caches. The answer is held with the
    content key of survey_inputs and the time it was made; a hit needs the same key and an answer
    younger than DIGEST_MAX_AGE, which bounds what an input the key does not name (an exported
    host-apply file) can make stale. The hook that runs this on every prompt then costs a hash.

    Returns:
        (lines, failed) as survey_lines gives them.

    """
    if root.resolve() != default_root().resolve():
        lines, failed, _ = survey_lines(root, digest=digest)
        return lines, failed
    key = cachestore.content_key(survey_inputs(root, digest=digest))
    path = cachestore.user_dir() / DIGEST_FILE
    try:
        held: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        held = None
    if isinstance(held, dict) and held.get("key") == key:
        at, said, bad = held.get("at"), held.get("lines"), held.get("failed")
        fresh = isinstance(at, float) and time.time() - at < DIGEST_MAX_AGE
        if fresh and isinstance(said, list) and isinstance(bad, int):
            return [str(line) for line in said], bad
    lines, failed, _ = survey_lines(root, digest=digest)
    body = json.dumps({"key": key, "at": time.time(), "lines": lines, "failed": failed})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{DIGEST_FILE}.{os.getpid()}")
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return lines, failed
    return lines, failed


def run_survey(root: Path, *, digest: bool, dump: str | None) -> int:
    """Print the fleet survey and give the exit code (nemik:W763).

    An unchanged fleet answers from the last run; a `dump` needs the merged graph, so it always
    surveys.

    Returns:
        How many queues violate or are unreadable; main turns it into the exit code.

    """
    if dump:
        lines, failed, merged = survey_lines(root, digest=digest)
        merged.serialize(destination=dump, format="turtle")
    else:
        lines, failed = cached_survey(root, digest=digest)
    for line in lines:
        print(line)
    return failed


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="nemik-check", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument("--dump", type=Path, help="write the merged graph as Turtle")
    ap.add_argument(
        "--realizability",
        action="store_true",
        help="print each live waypoint's realizability coordinate and residue ledger "
        "(mtools' policy under the pinned opa); exit 2 when a queue could not be judged",
    )
    ap.add_argument(
        "--committed",
        nargs="*",
        metavar="REPO",
        help="print the queue provenance lines and exit 4 when any named repo (none named: every "
        "repo) is read from an uncommitted or untracked queue: a claim about a peer reaches only "
        "as far as its last commit (nemik:W272, gcalculus:W224). Validates nothing.",
    )
    ap.add_argument(
        "--letters",
        action="store_true",
        help="check every letter under <repo>/inbox is addressed to that repo (its first line "
        "`from → to:`); exit 5 when one is misdelivered. Reads the receiving side only; validates "
        "nothing else (nemik:W271, gcalculus:W224)",
    )
    ap.add_argument(
        "--fold",
        action="store_true",
        help="with --letters: also list, as --add commands, every letter no waypoint of its repo "
        "cites (a letter is a waypoint's evidence in file form; nemik:W277). Applies nothing.",
    )
    ap.add_argument(
        "--repo",
        metavar="REPO",
        help="with --letters --fold, or --integrity: only this repo's inbox or findings (each repo "
        "works its own; "
        "nemik:W282)",
    )
    ap.add_argument(
        "--older-than",
        type=int,
        metavar="DAYS",
        help="with --letters --fold: an uncited letter whose file name is dated more than DAYS "
        "days ago is stale (listed as an archive `mv`), not live",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="with --letters --fold: carry out the plan: mint each live letter's waypoint through "
        "mikemol-paths-forward and move each stale letter into its inbox's archive/ (nemik:W301)",
    )
    ap.add_argument(
        "--integrity",
        dest="report",
        action="store_const",
        const="integrity",
        help="dry run: for each enables edge that leaves the subtree its card waits behind "
        "(nemik:W693), print the count per repo and the two fixes as commands, drop the edge or "
        "add the blocked_on; applies nothing. Each repo's session chooses",
    )
    ap.add_argument(
        "--unmanifested",
        dest="report",
        action="store_const",
        const="unmanifested",
        help="print the manifest ratchet as it should stand now (nemik:W685): each repo's ready "
        "cards with no manifest, never above what rank-weights.toml [manifest_ratchet] "
        "declares; applies nothing, the table is lowered by writing this output there",
    )
    ap.add_argument(
        "--ready-neither",
        dest="report",
        action="store_const",
        const="ready-neither",
        help="list the ready cards untouched for longer than 9 in 10 finished small cards took "
        "(nemik:W489), the bound learned from every queue; --repo REPO limits it to one repo",
    )
    ap.add_argument(
        "--digest",
        action="store_true",
        help="print each Info message several cards share once, with the count (the "
        "per-prompt hook digest, nemik:W641); Warnings and Violations stay in full. "
        "Without it, one row per card",
    )
    args = ap.parse_args(argv)
    if args.realizability:
        sys.exit(_realizability(args.root))
    if args.letters:
        from nemik.letters import report

        said, code = report(
            args.root,
            {repo for repo, _ in workstream_files(args.root, QUEUE)},
            args.fold,
            args.repo,
            args.older_than,
            args.apply,
        )
        print("\n".join(said))
        sys.exit(code)
    if args.committed is not None:
        sys.exit(committed_verdict(args.root, set(args.committed)))
    dry = report_mode(args.report, args.root, args.repo)
    if dry is not None:
        sys.exit(dry)

    for line in provenance(args.root):
        print(line)
    digest: bool = args.digest
    failed = run_survey(args.root, digest=digest, dump=args.dump)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
