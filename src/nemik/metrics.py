# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik-metrics: print nemik's state as Prometheus text exposition (for vmagent's import).

    nemik_waypoints{repo,state}              waypoints per OSLC state (ready|working|blocked|done|dropped)
    nemik_waypoints_minted{repo,during}      waypoints by mtools' minted_during (tick|interrupt);
                                             absent on waypoints minted before mtools 2e21902
    nemik_findings{repo,severity}            SHACL results per severity (Violation|Warning|Unreadable)
    nemik_prompts_total{repo,source,class}   prompts recorded by the global hook, where class is
                                             forecast (scheduled or operator-typed tick),
                                             interrupt (operator, peer), internal (subagent
                                             hand-backs, background notices: the session's own
                                             work returning), or unknown (a source string not in
                                             this module's own CLASS map -- a new hook source,
                                             not yet classified here)
    nemik_turns_total{repo}                  turns ended (Stop events)
    nemik_ledger_lines{repo,class,kind}      parsed ledger lines (mtools ledger.read) by effort class
    nemik_blocks_inbound{repo,claimed}       open waypoints in OTHER workstreams waiting on repo;
                                             claimed="false" when no waypoint of repo names them
    nemik_waiting_on{repo,state}             open waypoints elsewhere waiting on repo, by repo's
                                             liveness (asleep|idle|awake|unknown)
    nemik_pathsforward_adoption{repo,state}  1 per repo: declared|owner|missing|no-pyproject|unobservable
    nemik_ledger_unparsed{repo}              legacy/malformed ledger lines mtools returned unparsed
    nemik_realizability_waypoints{repo,coordinate}
                                             live waypoints per realizability coordinate
                                             (none|constructible|reachable|observable|coverable),
                                             judged by mtools' policy under the pinned opa
    nemik_realizability_unjudged{repo}       1 for a repo whose queue could not be judged (no pinned
                                             opa, an unreadable queue): absent coordinates are
                                             "not checked", never "clean"

    nemik_operator_salience{repo}            flow salience the repo's needs-you operator asks hold back,
                                             summed (what the operator owes its work; W300)
    nemik_operator_asks{repo}                how many needs-you asks that is
    nemik_warrant_debt{repo}                 open cards claiming an operator ruling in prose, no
                                             warrant (UnwarrantedRulingShape, W597); to 0 (W607)
    nemik_repo_tier{repo}                    the repo's burn-down tier as its place in the order, 0
                                             first (rank-weights.toml [tiers], W600); no gate
    nemik_waypoint_age_seconds{repo,state,quantile}
                                             age of the open waypoints per state, from issued_at:
                                             quantile 0.5 is the median, 1 the oldest (W270)

Pushing is not nemik's job: luthen hosts the push path, which admits metric names only when
its policy entails them. This command prints, and the host decides what to import.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from mikemol.pathsforward.lock import stamp
from mikemol.pathsforward.opa_eval import OpaUnavailableError
from mikemol.pathsforward.store import UnreadableStateError
from rdflib import RDF, Graph
from rdflib.namespace import PROV

from nemik import tiers
from nemik.adapter import BASE, NEMIK, OSLC_CM, ledger_graph
from nemik.blocks import inbound, ref
from nemik.check import LEDGER, QUEUE, default_root, survey, workstream_files
from nemik.realize import verdicts
from nemik.wake import read_liveness, roster

TYPE_LINE_WORDS = 3  # "# TYPE", the metric name, its kind

CLASS = {
    "tick": "forecast",
    "operator-tick": "forecast",
    "operator": "interrupt",
    "peer": "interrupt",
    "subagent": "internal",
    "background": "internal",
}


def spool_path() -> Path:
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(state) / "nemik" / "events.jsonl"


def label(**kv: str) -> str:
    return "{" + ",".join(f'{k}="{v}"' for k, v in kv.items()) + "}"


def realizability_lines(root: Path) -> list[str]:
    """One gauge row per repo and coordinate; a queue that cannot be judged is flagged, not zeroed."""
    out = ["# TYPE nemik_realizability_waypoints gauge"]
    out.append("# TYPE nemik_realizability_unjudged gauge")
    now = stamp(datetime.now(UTC))
    for repo, path in workstream_files(root, QUEUE):
        try:
            found = verdicts(repo, path, root, now)
        except (OpaUnavailableError, UnreadableStateError):
            out.append(f"nemik_realizability_unjudged{label(repo=repo)} 1")
            continue
        by_level = Counter(str(v.get("level")) for v in found)
        for level, n in sorted(by_level.items()):
            out.append(
                f"nemik_realizability_waypoints{label(repo=repo, coordinate=level)} {n}"
            )
    return out


def operator_lines(g: Graph) -> list[str]:
    """nemik:W300: per repo, the flow salience its needs-you operator asks hold back, summed, and how
    many asks that is: what the operator owes that repo's work, in nemik-rank's units."""
    from nemik.blocks import operator_asks, with_salience

    held: dict[str, float] = {}
    count: dict[str, int] = {}
    for ask in with_salience(g, operator_asks(g)):
        if ask["category"] != "needs-you":
            continue
        repo = str(ask["ref"]).partition(":")[0]
        held[repo] = held.get(repo, 0.0) + float(ask["salience"])
        count[repo] = count.get(repo, 0) + 1
    out = ["# TYPE nemik_operator_salience gauge", "# TYPE nemik_operator_asks gauge"]
    for repo in sorted(held):
        out.append(f"nemik_operator_salience{label(repo=repo)} {held[repo]:.2f}")
        out.append(f"nemik_operator_asks{label(repo=repo)} {count[repo]}")
    return out


def only_families(lines: list[str], names: list[str]) -> list[str]:
    """Keep the TYPE lines and samples of the named metric families (nemik:W607).

    luthen's host job registers metric families one at a time, so what it pushes must be exactly
    those; the family list lives with the producer, passed as repeated `--family NAME`.

    Args:
        lines: The exposition lines.
        names: The family names to keep.

    Returns:
        The lines of those families, in their original order.

    """

    def family(line: str) -> str:
        words = line.split()
        if line.startswith("# TYPE") and len(words) >= TYPE_LINE_WORDS:
            return words[2]
        return line.split("{", 1)[0].split(" ", 1)[0]

    return [line for line in lines if family(line) in names]


def warrant_lines(g: Graph) -> list[str]:
    """nemik:W607: per repo, the open cards that claim an operator ruling and have no warrant.

    The warrant debt (nemik:W597's UnwarrantedRulingShape): a series to ratchet down to zero as
    the rulings gain transcript records. Every repo with a queue is listed, so zero is a value,
    not an absent series.

    Args:
        g: The merged queue graph.

    Returns:
        The gauge's TYPE line and one sample per repo.

    """
    repos = sorted({ref(n).partition(":")[0] for n in g.subjects(OSLC_CM.state, None)})
    claims = g.subjects(NEMIK.claimsRuling, None)
    debt = Counter(ref(n).partition(":")[0] for n in claims)
    out = ["# TYPE nemik_warrant_debt gauge"]
    out += [f"nemik_warrant_debt{label(repo=repo)} {debt[repo]}" for repo in repos]
    return out


def tier_lines(g: Graph) -> list[str]:
    """nemik:W600: each repo's burn-down tier as a gauge: its position in the order, 0 first.

    Args:
        g: The merged queue graph.

    Returns:
        The gauge's TYPE line and one sample per repo. The tier is the value, not a label, so a
        tier change leaves no stale series (luthen-observability's cardinality caveat).

    """
    declared = tiers.load()
    repos = sorted({ref(n).partition(":")[0] for n in g.subjects(OSLC_CM.state, None)})
    out = ["# TYPE nemik_repo_tier gauge"]
    for repo in repos:
        tier = declared.get(repo, tiers.UNLISTED)
        out.append(f"nemik_repo_tier{label(repo=repo)} {tiers.rank(tier)}")
    return out


def health_lines(g: Graph) -> list[str]:
    """nemik:W317: each repo's health as a gauge: 0 green, 1 amber, 2 red (nemik.health, from the
    thresholds `[health]` declares in rank-weights.toml)."""
    from nemik.blocks import ref
    from nemik.health import STATUSES, health, thresholds

    limits = thresholds()
    repos = sorted({ref(n).partition(":")[0] for n in g.subjects(OSLC_CM.state, None)})
    out = ["# TYPE nemik_repo_health gauge"]
    for repo in repos:
        level = STATUSES.index(health(g, repo, limits).status)
        out.append(f"nemik_repo_health{label(repo=repo)} {level}")
    return out


def age_lines(repo: str, g: Graph, now: datetime) -> list[str]:
    """nemik:W270: how long the open waypoints of `repo` have existed, per OSLC state, as a
    summary-style gauge: quantile 0.5 is the median age and quantile 1 the oldest. Per-waypoint
    series would be thousands of labels, and the question ("how long has the oldest one sat") is
    the quantile. Age runs from `issued_at`; a waypoint with none is left out, not counted as new."""
    from rdflib.namespace import DCTERMS

    ages: dict[str, list[float]] = {}
    for node, _, created in g.triples((None, DCTERMS.created, None)):
        state = g.value(node, OSLC_CM.state)
        if state is None:
            continue
        try:
            born = datetime.fromisoformat(str(created))
        except ValueError:
            continue
        name = str(state).rsplit("#", 1)[-1].lower()
        if name in ("done", "dropped"):
            continue
        ages.setdefault(name, []).append(max(0.0, (now - born).total_seconds()))
    out: list[str] = []
    for name, seen in sorted(ages.items()):
        seen.sort()
        for quantile, value in (("0.5", seen[len(seen) // 2]), ("1", seen[-1])):
            out.append(
                f"nemik_waypoint_age_seconds{label(repo=repo, state=name, quantile=quantile)}"
                f" {value:.0f}"
            )
    return out


class _Options(argparse.Namespace):
    """The parsed command line, with the one option the filter reads typed."""

    family: list[str] | None


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="nemik-metrics", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument("--spool", type=Path, default=spool_path())
    ap.add_argument(
        "--family",
        action="append",
        metavar="NAME",
        help="print only this metric family (repeatable): the host job pushes the registered ones",
    )
    args = ap.parse_args(argv, namespace=_Options())

    out = [
        "# TYPE nemik_waypoints gauge",
        "# TYPE nemik_waypoints_minted gauge",
        "# TYPE nemik_findings gauge",
        "# TYPE nemik_waypoint_age_seconds gauge",
    ]
    now = datetime.now(UTC)
    for repo, g, findings in survey(args.root):
        states: Counter[str] = Counter()
        if g is not None:
            out += age_lines(repo, g, now)
        if g is not None:
            for _, _, st in g.triples((None, OSLC_CM.state, None)):
                states[str(st).rsplit("#", 1)[-1].lower()] += 1
            states["dropped"] = sum(1 for _ in g.subjects(RDF.type, NEMIK.Dropped))
        for name, n in sorted(states.items()):
            out.append(f"nemik_waypoints{label(repo=repo, state=name)} {n}")
        if g is not None:
            for during, n in sorted(
                Counter(str(o) for o in g.objects(None, NEMIK.mintedDuring)).items()
            ):
                out.append(
                    f"nemik_waypoints_minted{label(repo=repo, during=during)} {n}"
                )
        for sev, n in sorted(Counter(sev for sev, _, _ in findings).items()):
            out.append(f"nemik_findings{label(repo=repo, severity=sev)} {n}")

    merged = Graph()
    for _, g, _ in survey(args.root):
        if g is not None:
            merged += g
    out.append("# TYPE nemik_blocks_inbound gauge")
    inb = Counter(
        (b["blocker"], str(bool(b["claimed_by"])).lower()) for b in inbound(merged)
    )
    for (repo, claimed), n in sorted(inb.items()):
        out.append(f"nemik_blocks_inbound{label(repo=repo, claimed=claimed)} {n}")

    out.append("# TYPE nemik_pathsforward_adoption gauge")
    for ws, _, state in sorted(
        merged.triples((None, NEMIK.pathsforwardAdoption, None))
    ):
        out.append(
            f"nemik_pathsforward_adoption{label(repo=str(ws).removeprefix(BASE), state=str(state))} 1"
        )
    out.append("# TYPE nemik_waiting_on gauge")
    live, _ = read_liveness(args.root, None)
    for r in roster(merged, live):
        out.append(
            f"nemik_waiting_on{label(repo=r['repo'], state=r['state'])} {len(r['waiting'])}"
        )
    out += operator_lines(merged)
    out += health_lines(merged)
    out += warrant_lines(merged)
    out += tier_lines(merged)
    out += realizability_lines(args.root)

    prompts: Counter[tuple[str, str, str]] = Counter()
    turns: Counter[str] = Counter()
    if args.spool.exists():
        for raw in args.spool.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(raw)
            except json.JSONDecodeError:
                continue
            repo = e.get("repo") or "none"
            if e.get("event") == "UserPromptSubmit":
                src = e.get("source") or "unknown"
                prompts[(repo, src, CLASS.get(src, "unknown"))] += 1
            elif e.get("event") == "Stop":
                turns[repo] += 1
    out.append("# TYPE nemik_prompts_total counter")
    for (repo, src, cls), n in sorted(prompts.items()):
        out.append(
            f"nemik_prompts_total{label(repo=repo, source=src, **{'class': cls})} {n}"
        )
    out.append("# TYPE nemik_turns_total counter")
    for repo, n in sorted(turns.items()):
        out.append(f"nemik_turns_total{label(repo=repo)} {n}")
    out += ["# TYPE nemik_ledger_lines gauge", "# TYPE nemik_ledger_unparsed gauge"]
    for repo, path in workstream_files(args.root, LEDGER):
        g, unparsed = ledger_graph(repo, path)
        lines = Counter(
            (str(c), str(k))
            for a in g.subjects(RDF.type, PROV.Activity)
            for c in g.objects(a, NEMIK.effortClass)
            for k in g.objects(a, NEMIK.kind)
        )
        for (cls, kind), n in sorted(lines.items()):
            out.append(
                f"nemik_ledger_lines{label(repo=repo, kind=kind, **{'class': cls})} {n}"
            )
        out.append(f"nemik_ledger_unparsed{label(repo=repo)} {unparsed}")
    print("\n".join(only_families(out, args.family) if args.family else out))


if __name__ == "__main__":
    main()
