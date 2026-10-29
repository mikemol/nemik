# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Cross-workstream blocks, read from both sides.

A waypoint blocked on another workstream is only actionable when both agents can name the same
thing: the blocked agent cites `<repo>:W<n>`, and the blocker knows which of its own waypoints
is the block. `blocked_on` often names only a repo or a session. This module finds, for each such
block, the blocker's waypoint that CLAIMS it, meaning one that `enables` the blocked waypoint
(`repo:W<n>` is legal in enables since mtools 9236d5e) or was `caused_by` it. Blocks with no claim
are the ones nobody can reference yet.

The `nemik-inbound` and `nemik-operator` commands are in `nemik.blocks_cli`: they need
`nemik.check.survey`, and `check` imports `annotate` from here.
"""

from __future__ import annotations

import operator
import re
from typing import TYPE_CHECKING, Any

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV

from nemik.adapter import BASE, NEMIK, OSLC_CM

if TYPE_CHECKING:
    from rdflib.term import Node

CAL_BLOCK = re.compile(
    r"cal:[a-z][a-z0-9-]{0,31}/\S+"
)  # same form as nemik.calendars.CAL_REF
# nemik:W256: host:<id> is a condition, a row of luthen's host-apply export (nemik.hostapply).
HOST_BLOCK = re.compile(r"host:[A-Za-z0-9][A-Za-z0-9._@-]*")


def ref(node: Node) -> str:
    """Name the citable form of a waypoint IRI: `<repo>:W<n>`."""
    repo, _, sym = str(node).removeprefix(BASE).partition("/")
    return f"{repo}:{sym}"


def _repo(node: Node) -> str:
    return str(node).removeprefix(BASE).partition("/")[0]


def claims_of(g: Graph, node: Node, blocker: str) -> set[Node]:
    """Find the blocker repo's cards that claim a wait.

    Args:
        g: The merged graph.
        node: The waiting card.
        blocker: The repo it waits on.

    Returns:
        The blocker's cards that enable the waiter or were caused by it.

    """
    return {w for w in g.subjects(NEMIK.enables, node) if _repo(w) == blocker} | {
        w for w in g.subjects(PROV.wasInformedBy, node) if _repo(w) == blocker
    }


def bare_wait_edges(g: Graph) -> list[tuple[Node, Node]]:
    """Resolve each open card blocked on a bare repo name to its claims (nemik:W576).

    A wait on `linux-sources` names no card, so it draws no card-to-card edge and a ring through it
    went unseen for days. The wait resolves to that repo's cards that claim it (`claims_of`): the
    waiter cannot move before one of them does, so the claim is a prerequisite of the waiter.

    Args:
        g: The merged graph.

    Returns:
        Each (claim, waiter) pair.

    """
    found: list[tuple[Node, Node]] = []
    for node, _, target in g.triples((None, NEMIK.waitsFor, None)):
        if (target, RDF.type, NEMIK.Workstream) not in g:
            continue
        if (node, OSLC_CM.state, NEMIK.Done) in g or _repo(target) == _repo(node):
            continue
        found.extend(
            (claim, node)
            for claim in sorted(claims_of(g, node, _repo(target)), key=str)
        )
    return found


def inbound(g: Graph, letters: bool = False) -> list[dict[str, Any]]:
    """Every open waypoint waiting on another workstream, with the blocker's claiming waypoints.

    With `letters`, each row also carries the letter files the waiting waypoint cites (nemik:W275):
    the CLI shows them; the served and published documents leave them out, since a file name can
    say more than the title it sits beside.
    """
    out: list[dict[str, Any]] = []
    for node, _, target in g.triples((None, NEMIK.waitsFor, None)):
        if (node, OSLC_CM.state, NEMIK.Done) in g:
            continue
        if (target, RDF.type, NEMIK.Workstream) in g:
            blocker = _repo(target)
            named = None
        elif (target, RDF.type, OSLC_CM.ChangeRequest) in g or (
            target,
            RDF.type,
            NEMIK.Dropped,
        ) in g:
            blocker = _repo(target)
            named = target
        else:
            continue  # the operator, or a target outside the graph
        if blocker == _repo(node):
            continue
        claims = claims_of(g, node, blocker)
        if named is not None:
            claims.add(named)
        row: dict[str, Any] = {
            "blocked": ref(node),
            "title": str(g.value(node, DCTERMS.title) or ""),
            "blocked_on": sorted(str(o) for o in g.objects(node, NEMIK.blockedOn)),
            "blocker": blocker,
            "claimed_by": sorted(ref(c) for c in claims),
        }
        if letters:
            row["letters"] = sorted(str(o) for o in g.objects(node, NEMIK.letter))
        out.append(row)
    return sorted(out, key=operator.itemgetter("blocker", "blocked", "claimed_by"))


def ready_behind_open(g: Graph) -> dict[Node, list[Node]]:
    """nemik:W465: each ready card an open card enables, with those enablers, leaving out the
    umbrellas (2+ open children of its own repo) that ReadyUmbrella already reports. A pure reading
    of the graph, so annotate (the check) and serve (the view's mark, nemik:W477) agree.
    """
    out: dict[Node, list[Node]] = {}
    for node in g.subjects(OSLC_CM.state, NEMIK.Ready):
        enablers = [
            c
            for c in g.subjects(NEMIK.enables, node)
            if (c, OSLC_CM.state, None) in g and (c, OSLC_CM.state, NEMIK.Done) not in g
        ]
        own = [c for c in enablers if _repo(c) == _repo(node)]
        if enablers and len(own) < 2:
            out[node] = sorted(enablers, key=str)
    return out


def ready_unmanifested(g: Graph) -> list[Node]:
    """nemik:W684: each ready leaf that declares no manifest, the cards ManifestShape reports.

    A leaf is a ready card no open card enables. Without a manifest it cannot be stacked
    (nemik:W613), so the view draws it as waiting for one instead of as pickable. A pure reading of
    the graph, so the check and the view agree.

    Args:
        g: The merged queue graph.

    Returns:
        The cards, in node order.

    """
    out: list[Node] = []
    for node in g.subjects(OSLC_CM.state, NEMIK.Ready):
        if (node, NEMIK.plannedPath, None) in g:
            continue
        open_enablers = [
            c
            for c in g.subjects(NEMIK.enables, node)
            if (c, OSLC_CM.state, None) in g and (c, OSLC_CM.state, NEMIK.Done) not in g
        ]
        if not open_enablers:
            out.append(node)
    return sorted(out, key=str)


def unmanifested_by_repo(g: Graph) -> dict[str, int]:
    """nemik:W685: how many ready cards of each repo declare no manifest of planned changes.

    A ready card with no manifest cannot be stacked (nemik:W613), so the view shows it as pickable
    while it is not. ManifestShape reports only the leaves; this counts every ready card, which is
    what the picture promises the operator.

    Args:
        g: The merged queue graph.

    Returns:
        repo -> count, for every repo that has a workstream node (zero where all are manifested).

    """
    counts: dict[str, int] = {
        str(ws).removeprefix(BASE): 0 for ws in g.subjects(RDF.type, NEMIK.Workstream)
    }
    for node in g.subjects(OSLC_CM.state, NEMIK.Ready):
        if (node, NEMIK.plannedPath, None) not in g:
            repo = ref(node).partition(":")[0]
            counts[repo] = counts.get(repo, 0) + 1
    return counts


def over_ratchet(
    counts: dict[str, int], declared: dict[str, int]
) -> dict[str, tuple[int, int]]:
    """nemik:W685: the repos whose count passes what the ratchet declares for them.

    The ratchet is measured data (rank-weights.toml [manifest_ratchet]), never a typed cap, and it
    only falls: a repo the file does not name is declared at zero.

    Args:
        counts: repo -> today's count.
        declared: repo -> the count the ratchet allows.

    Returns:
        repo -> (count, declared) for each repo over it, sorted by repo.

    """
    return {
        repo: (n, declared.get(repo, 0))
        for repo, n in sorted(counts.items())
        if n > declared.get(repo, 0)
    }


def lowered_ratchet(counts: dict[str, int], declared: dict[str, int]) -> dict[str, int]:
    """nemik:W685: what the ratchet file should hold now: each repo's count, never above before.

    Args:
        counts: repo -> today's count.
        declared: repo -> the count the ratchet allows today.

    Returns:
        repo -> min(count, declared); a repo not yet declared takes its count.

    """
    return {repo: min(n, declared.get(repo, n)) for repo, n in sorted(counts.items())}


def node_marks(g: Graph) -> dict[str, dict[str, bool]]:
    """nemik:W477, W684: the flags the view draws on a ready card, by node id.

    Args:
        g: The merged queue graph.

    Returns:
        For each ready card that waits on an open card `behind_open`, and for each ready leaf with
        no manifest `needs_manifest`, both true; a card with neither has no entry.

    """
    marks: dict[str, dict[str, bool]] = {}
    for node in ready_behind_open(g):
        marks.setdefault(str(node), {})["behind_open"] = True
    for node in ready_unmanifested(g):
        marks.setdefault(str(node), {})["needs_manifest"] = True
    return marks


SHOWN_SEVERITIES = ("Warning", "Violation")


def warnings_by_card(
    findings: dict[str, list[tuple[str, str, str]]],
) -> dict[str, dict[str, list[dict[str, str]]]]:
    """nemik:W687: each card's Warnings and Violations, keyed by node id, for the view's badge.

    The operator (2026-10-18, 695f3e0a line 79877) ruled that a card that throws warnings on the CLI
    carries a visual indicator in the UI. The CLI prints nemik-check's findings; this groups the
    same rows by card so the payload carries exactly what the CLI says, and a new shape reaches the
    view with no further work. Info rows stay on the CLI (hundreds, and not warnings).

    Args:
        findings: nemik-check's rows by repo: (severity, focus symbol, message). A repo-level row
            has the symbol `--` and belongs to no card.

    Returns:
        node id -> {"warnings": [{"severity", "message"}, ...]}, only for cards that have any.

    """
    out: dict[str, dict[str, list[dict[str, str]]]] = {}
    for repo, rows in findings.items():
        for severity, symbol, message in rows:
            if severity in SHOWN_SEVERITIES and symbol != "--":
                card = out.setdefault(f"{BASE}{repo}/{symbol}", {"warnings": []})
                card["warnings"].append({"severity": severity, "message": message})
    return out


def node_flags(
    g: Graph, findings: dict[str, list[tuple[str, str, str]]]
) -> dict[str, dict[str, object]]:
    """nemik:W477, W684, W687: everything the view adds to a card's node beyond the graph, by id.

    Args:
        g: The merged queue graph.
        findings: nemik-check's rows by repo: (severity, focus symbol, message).

    Returns:
        node id -> its flags (behind_open, needs_manifest) and its warnings, for each card that
        has any.

    """
    out: dict[str, dict[str, object]] = {k: dict(v) for k, v in node_marks(g).items()}
    for node, held in warnings_by_card(findings).items():
        out.setdefault(node, {}).update(held)
    return out


def dependency_cycles(g: Graph) -> list[tuple[Node, ...]]:
    """nemik:W484 (mtools:W1134 found a ring of three ready cards blocked into a deadlock): every
    cycle of open cards that wait on or enable one another, named once from its earliest card, as
    the fleet's shared walker (mikemol.frontier.walk, mtools:W1127) finds it. A ring can never land.
    """
    from mikemol.frontier.walk import frontier as walk

    cards = set(g.subjects(OSLC_CM.state, None))
    edges = {(str(a), str(b)) for a, _, b in g.triples((None, NEMIK.enables, None))}
    edges |= {(str(b), str(a)) for a, _, b in g.triples((None, NEMIK.waitsFor, None))}
    edges |= {(str(claim), str(waiter)) for claim, waiter in bare_wait_edges(g)}
    names = {str(n) for n in cards}
    verdict = walk(
        sorted(names),
        sorted((a, b) for a, b in edges if a in names and b in names),
        lambda s: (URIRef(s), OSLC_CM.state, NEMIK.Done) in g,
    )
    return [tuple(URIRef(s) for s in ring) for ring in verdict.cycles]


def annotate(g: Graph) -> None:
    """Mark unclaimed blocks, operator blocks by category, and blocks that resolve to no party."""
    # A blocked waypoint whose blocked_on names nothing nemik can resolve (no workstream, waypoint
    # or operator) draws no edge at all; the operator ruled that a defect (2026-09-26).
    for node in g.subjects(OSLC_CM.state, NEMIK.Blocked):
        human = (
            str(g.value(node, NEMIK.blockedKind) or "") == "human"
        )  # drawn to an operator lane
        if (node, NEMIK.waitsFor, None) not in g and not human:
            for text in g.objects(node, NEMIK.blockedOn):
                # nemik:W183: cal:<label>/<uid> is a condition, an event on the operator's calendar
                # (nemik-days resolves it host-side). Checked by form only: the check runs where the
                # calendars are not, and must never read them (nemik:W161).
                # nemik:W256: host:<id> likewise by form here; `check.survey` then holds it against
                # the host-apply export, where the export is readable.
                cited = str(text).strip()
                # nemik:W520 (luthen-observability, 2026-10-15): the writer refuses a
                # witnessed card that is ready and tells its owner to block it on
                # `nemik-witnesses`, the process that closes it. That is a party, for a card
                # that has a witness (the graph keeps only its hash, as NEMIK.weather); for
                # any other card it still names nothing.
                witnessed = (
                    cited == "nemik-witnesses" and (node, NEMIK.weather, None) in g
                )
                if not (
                    CAL_BLOCK.fullmatch(cited)
                    or HOST_BLOCK.fullmatch(cited)
                    or witnessed
                ):
                    g.add((node, NEMIK.unresolvedBlocker, text))

    # nemik:W41, W144, W436: umbrella blocks and ready umbrellas are SPARQL constraints in
    # shapes.ttl (nemik:W529), UmbrellaBlockShape and ReadyUmbrellaShape.
    # nemik:W465: the one-enabler case the umbrella rule leaves out (mtools:W1115 sat ready behind
    # open W1122, W1116 behind W1115). The flow model already treats it as waiting, so its salience
    # reads blank while its fill says ready. Ready only, as mtools:W1131's fix: a working card is
    # being done, so it is left alone.
    for node, enablers in ready_behind_open(g).items():
        for c in enablers:
            g.add((node, NEMIK.readyBehindOpen, c))

    # A block on a waypoint that has already landed (done, or dropped to residue) is stale: the
    # waiter should have been lifted to ready, or its blocked_on trimmed (nemik:W110, paperkit
    # found 8 such in its own queue, some a day old). All of them landed means mis-stated as
    # blocked.
    for node in set(g.subjects(NEMIK.waitsFor, None)):
        if (node, OSLC_CM.state, NEMIK.Done) in g:
            continue
        landed = [
            t
            for t in g.objects(node, NEMIK.waitsFor)
            if (t, OSLC_CM.state, NEMIK.Done) in g or (t, RDF.type, NEMIK.Dropped) in g
        ]
        # nemik:W529: the per-blocker finding is a SPARQL constraint (LandedBlockerShape).
        if landed and len(landed) == len(set(g.objects(node, NEMIK.blockedOn))):
            g.add((node, NEMIK.allBlockersLanded, Literal(True)))

    # nemik:W529: a blocked_on entry that is a symbol with prose run on (nemik:W110) is the
    # MalformedBlockerShape SPARQL constraint, not a marker.
    for a in operator_asks(g):
        repo, _, sym = a["ref"].partition(":")
        g.add(
            (URIRef(f"{BASE}{repo}/{sym}"), NEMIK.operatorAsk, Literal(a["category"]))
        )
    for b in inbound(g):
        if not b["claimed_by"]:
            repo, _, sym = b["blocked"].partition(":")
            g.add(
                (
                    URIRef(f"{BASE}{repo}/{sym}"),
                    NEMIK.unclaimedBlockOn,
                    URIRef(f"{BASE}{b['blocker']}"),
                )
            )


# ---- Blocks on the operator -------------------------------------------------------------------
#
# Most blocks that reach the operator are not requests for the operator: the answer is already
# recorded, the wait is really on a condition, or the same decision is asked from several places.
# These rules read the blocked_on text agents actually write (measured 2026-09-26, 29 blocks) and
# sort each block into one category. They are a stated reading, not a verdict: the fix for an
# "unstated" block is for its agent to state the ask.

# The skill's explicit form ("operator: decide ..." / "operator: act ...") is the agent's own
# statement of the ask, so it wins over every keyword reading below: "decide whether ... how
# sourced records an operator ruling" is a question about rulings, not a recorded one.
EXPLICIT = re.compile(r"^\s*operator\s*:\s*(decide|act)\b", re.IGNORECASE)
# Past-tense forms only: a noun like "ruling" appears in questions about rulings too.
ANSWERED = re.compile(
    r"\b(ruled|keep holding|approved|go-ahead given|decided)\b", re.IGNORECASE
)
CONDITION = re.compile(
    r"^\s*(event:|a green tree|once\b|when\b|after\b)|\bresume when\b|\bonce the\b",
    re.IGNORECASE,
)
DECISION = re.compile(
    r"\b(approv\w*|go\b|go-ahead|choice|choose|decide|decision|which|whether|confirm|restart|act|acts|"
    r"teardown|layout|owns|credential|push|commit)\b|\?",
    re.IGNORECASE,
)
BARE = re.compile(
    r"^\s*(the\s+)?(operator|user|mikemol|mike|human)\s*(\(\w+\))?\s*$", re.IGNORECASE
)

# nemik:W458 (github-8f, luthen-observability:W69 stood 93 ticks as "operator: act the host-root
# sudo
# applies" with nothing to run): an act ask carries the command in a standard shape, an
# `env -C <repo> <abs interpreter> -m <module>` line or a sudo-prefixed one. Without it the owner
# still owes the tool, and the ask is not the operator's yet.
COMMAND = re.compile(
    r"\benv\s+-C\s+\S+\s+/\S+\s+-m\s+\S+"
    r"|\bsudo\s+(?:-\S+\s+)*(?:/\S+|env\s+-C\b|systemctl\s+\w|python[\d.]*\s+-m\s+\S)"
)
# Only an act on a machine owes a command: "bring to orientation" or "check Gmail" is the
# operator's own errand, not an unwritten tool.
MACHINE_ACT = re.compile(
    r"\b(sudo|root|run|apply|applies|command|install|systemctl|reaper|restore|drill)\b",
    re.IGNORECASE,
)

CATEGORIES = ("needs-you", "no-command", "errand", "answered", "condition", "unstated")


def errand_repos(text: str | None = None) -> frozenset[str]:
    """nemik:W460: the repos whose machine-sounding acts are the operator's own errands ("apply for
    Medicaid", a "drill" session), declared under [errand] in rank-weights.toml: no tool to write.
    """
    import tomllib
    from importlib.resources import files

    if text is None:
        text = files("nemik.data").joinpath("rank-weights.toml").read_text()
    return frozenset(tomllib.loads(text).get("errand", {}).get("repos", []))


def operator_category(text: str) -> str:
    """Sort an operator block's text by what it asks.

    Returns:
        One of no-command, needs-you, answered, condition or unstated.

    """
    if m := EXPLICIT.match(text):
        if (
            m[1].lower() == "act"
            and MACHINE_ACT.search(text)
            and not COMMAND.search(text)
        ):
            return "no-command"
        return "needs-you"
    if ANSWERED.search(text):
        return "answered"
    if CONDITION.search(text):
        return "condition"
    if BARE.match(text):
        return "unstated"
    rest = re.sub(
        r"^\s*(operator|user|mikemol|mike|human)\s*[:(]?", "", text, flags=re.IGNORECASE
    )
    # nemik:W27: deliberately asymmetric, not a length proxy for "has a real ask". A short
    # scrap with no decide/act keyword is genuinely ambiguous -- unstated. But several words of
    # free text, even with no decide/act verb, is read as needs-you rather than unstated: an
    # agent that bothered to write a sentence almost always wants something, and undercounting
    # here means a real ask silently drops off the operator's radar, which is worse than an
    # occasional over-alert. Only a truly bare blocked_on (BARE, above) reliably lands unstated.
    return (
        "needs-you" if DECISION.search(rest) or len(rest.split()) >= 3 else "unstated"
    )


def _ask_key(text: str) -> str:
    """Normalise an ask so the same decision asked from several repos groups together."""
    t = re.sub(
        r"^\s*(operator|user|mikemol|mike)\s*[:(]?\s*", "", text, flags=re.IGNORECASE
    ).lower()
    t = re.sub(r"\b(for|of|the|a|an|to)\b|[^a-z0-9 ]", " ", t)
    return " ".join(w for w in t.split() if w not in {"s", "approval", "approve"})[:40]


def waiting_behind(g: Graph, node: Node) -> set[Node]:
    """Every open waypoint, in any workstream, that waits on `node` directly or through others:
    it waits for it (blocked_on) or `node` enables it. So an operator ask held by one repo shows
    the work queued behind it in others (resumes:W1 behind life:W21, 2026-09-28).
    """
    seen: set[Node] = set()
    stack = [node]
    while stack:
        n = stack.pop()
        for w in set(g.subjects(NEMIK.waitsFor, n)) | set(g.objects(n, NEMIK.enables)):
            if (
                w not in seen
                and w != node
                and (w, OSLC_CM.state, None) in g
                and (w, OSLC_CM.state, NEMIK.Done) not in g
            ):
                seen.add(w)
                stack.append(w)
    return seen


# nemik:W1264 (github:W76, host retro R96): an 'operator: act' ask that names a root-shaped command
# is the host apply loop's to carry, unless the card says why it cannot ('apply loop cannot: ...').
_ROOT_SHAPED = re.compile(
    r"\bsudo\b|\broot\b|\bchown\b|\binstall\s+-d\b|\bmkfs\b|\bmount\b|\bsystemctl\s+--system\b",
    flags=re.IGNORECASE,
)
_ACT_ASK = re.compile(r"(?:^|\|\s*)operator:\s*act\b", flags=re.IGNORECASE)


def sudo_shaped(ask: str) -> bool:
    """Say whether an ask is an 'operator: act' that names a root-shaped command.

    Args:
        ask: The blocked_on texts of a card, joined by ' | '.

    Returns:
        True when one of them starts 'operator: act' and the text names sudo, root, chown,
        install -d, mkfs, mount or systemctl --system as a whole word.

    """
    return _ACT_ASK.search(ask) is not None and _ROOT_SHAPED.search(ask) is not None


def operator_asks(g: Graph) -> list[dict[str, Any]]:
    """Every open waypoint waiting on the operator, categorised, with duplicate asks grouped.

    nemik:W412: answered once per graph inside a build (health asks it once per repo); each caller
    gets its own copies of the rows, so a caller that annotates them touches nothing shared.
    """
    from nemik.index import index

    ix = index(g)
    if ix is None:
        return _operator_asks(g)
    if ix.operator_asks is None:
        ix.operator_asks = _operator_asks(g)
    return [dict(row) for row in ix.operator_asks]


def _operator_asks(g: Graph) -> list[dict[str, Any]]:
    from nemik.adapter import OPERATOR

    last: dict[Node, str] = {}
    for act in g.subjects(RDF.type, PROV.Activity):
        stamp = str(g.value(act, PROV.startedAtTime) or "")
        for wp in g.objects(act, PROV.used):
            last[wp] = max(last.get(wp, ""), stamp)
    out: list[dict[str, Any]] = []
    # On the operator: resolved to them, or declared blocked_kind human (e.g. "event: ...", "a
    # GREEN tree - operator RULED ...", which name a condition but were filed against the human).
    human = set(g.subjects(NEMIK.waitsFor, OPERATOR)) | {
        n
        for n in g.subjects(NEMIK.blockedKind, None)
        if str(g.value(n, NEMIK.blockedKind)) == "human"
        and (n, OSLC_CM.state, NEMIK.Blocked) in g
    }
    repos = {str(w).removeprefix(BASE) for w in g.subjects(RDF.type, NEMIK.Workstream)}
    errands = errand_repos()
    for node in human:
        if (node, OSLC_CM.state, NEMIK.Done) in g:
            continue
        texts = sorted(str(o) for o in g.objects(node, NEMIK.blockedOn))
        title = str(g.value(node, DCTERMS.title) or "")
        # A bare "operator" with the ask carried in a title that starts "OPERATOR: ..." (summit's
        # convention) states the ask there; read it rather than calling the block unstated.
        if all(BARE.match(t) for t in texts) and re.match(
            r"^\s*operator\b[^:]{0,60}:", title, re.IGNORECASE
        ):
            texts = [title]
        text = " | ".join(texts)
        cats = [operator_category(t) for t in texts] or ["unstated"]
        # the most actionable reading wins across several blocked_on values
        cat: str = next(
            c
            for c in ("needs-you", "no-command", "unstated", "condition", "answered")
            if c in cats
        )
        if cat == "no-command" and ref(node).partition(":")[0] in errands:
            cat = "errand"
        # nemik:W1264: the card says why the root apply loop could not carry it (nemik:W1263)
        excused = (node, NEMIK.applyLoopCannot, None) in g
        out.append(
            {
                "ref": ref(node),
                "title": str(g.value(node, DCTERMS.title) or ""),
                "ask": text,
                "apply_loop_cannot": excused,
                "sudo_shaped": sudo_shaped(text) and not excused,
                "category": cat,
                "ticks_blocked": int(str(g.value(node, NEMIK.ticksBlocked) or 0)),
                "last_activity": last.get(node, ""),
                "key": _ask_key(text) if cat == "needs-you" else "",
                "waiting": sorted(ref(w) for w in waiting_behind(g, node)),
                "dtstart": str(g.value(node, NEMIK.dtstart) or ""),
                "due": str(g.value(node, NEMIK.due) or ""),
                "alarms": sorted(str(a) for a in g.objects(node, NEMIK.alarm)),
                "rrule": str(g.value(node, NEMIK.rrule) or ""),
                "exdates": sorted(str(x) for x in g.objects(node, NEMIK.exdate)),
            }
        )
    groups: dict[str, set[str]] = {}
    for a in out:
        if a["key"]:
            groups.setdefault(a["key"], set()).add(a["ref"])
    by_ref = {a["ref"]: a for a in out}
    for a in out:
        same = set(groups.get(a.pop("key"), ())) - {a["ref"]}
        # an ask that names another blocked waypoint ("... for linux-sources W24 ...") is that ask
        for m in re.finditer(r"([\w.-]+)[: ]W(\d+)\b", a["ask"]):
            other = f"{m[1]}:W{m[2]}"
            if m[1] in repos and other in by_ref and other != a["ref"]:
                same.add(other)
                by_ref[other].setdefault("_named_by", set()).add(a["ref"])
        a["same_ask"] = same
    for a in out:
        a["same_ask"] = sorted(a["same_ask"] | a.pop("_named_by", set()))
    # close each group over itself, so every member lists every other
    for a in out:
        members = {a["ref"], *a["same_ask"]}
        for r in list(members):
            members |= set(by_ref[r]["same_ask"])
        a["same_ask"] = sorted(members - {a["ref"]})
    order = {c: i for i, c in enumerate(CATEGORIES)}
    return sorted(
        out, key=lambda a: (order[a["category"]], -a["ticks_blocked"], a["ref"])
    )


def with_salience(g: Graph, asks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """nemik:W298 (operator 2026-10-10: the waiting-on-operator machinery must carry the salience
    signal): how much demand waits behind each ask.

    Each ask is a card with no open prerequisite, so in the flow model it is ground: it absorbs the
    demand of the cards that need it, weighted by the class weights of rank-weights.toml (as
    seen from
    the ask's own repo). That absorbed salience is what answering the ask would release, in the same
    units as nemik-rank. An ask that itself needs another open card carries 0 (its demand flows to
    that card). Within a category the heaviest ask comes first; ticks blocked break ties.
    """
    from nemik.salience import audit

    solved: dict[str, dict[str, Any]] = {}
    for ask in asks:
        repo = str(ask["ref"]).partition(":")[0]
        if repo not in solved:
            solved[repo] = audit(g, repo).flow.salience
        ask["salience"] = round(float(solved[repo].get(ask["ref"], 0)), 2)
    order = {c: i for i, c in enumerate(CATEGORIES)}
    return sorted(
        asks,
        key=lambda a: (
            order[a["category"]],
            -a["salience"],
            -a["ticks_blocked"],
            a["ref"],
        ),
    )
