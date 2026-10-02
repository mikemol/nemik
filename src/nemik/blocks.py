"""Cross-workstream blocks, read from both sides.

A waypoint blocked on another workstream is only actionable when both agents can name the same
thing: the blocked agent cites `<repo>:W<n>`, and the blocker knows which of its own waypoints
is the block. `blocked_on` often names only a repo or a session. This module finds, for each such
block, the blocker's waypoint that CLAIMS it, meaning one that `enables` the blocked waypoint
(`repo:W<n>` is legal in enables since mtools 9236d5e) or was `caused_by` it. Blocks with no claim
are the ones nobody can reference yet.
"""

from __future__ import annotations

import re
from pathlib import Path

from rdflib import RDF, Graph, URIRef
from rdflib.namespace import DCTERMS, PROV

from nemik.adapter import BASE, NEMIK, OSLC_CM


_SYMBOLISH = re.compile(r"^([A-Za-z0-9_.-]+:)?W\d+\b")
_CLEAN_SYMBOL = re.compile(r"([A-Za-z0-9_.-]+:)?W\d+")


CAL_BLOCK = re.compile(r"cal:[a-z][a-z0-9-]{0,31}/\S+")  # same form as nemik.calendars.CAL_REF


def ref(node: URIRef) -> str:
    """The citable form of a waypoint IRI: `<repo>:W<n>`."""
    repo, _, sym = str(node).removeprefix(BASE).partition("/")
    return f"{repo}:{sym}"


def _repo(node: URIRef) -> str:
    return str(node).removeprefix(BASE).partition("/")[0]


def inbound(g: Graph) -> list[dict]:
    """Every open waypoint waiting on another workstream, with the blocker's claiming waypoints."""
    out = []
    for node, _, target in g.triples((None, NEMIK.waitsFor, None)):
        if (node, OSLC_CM.state, NEMIK.Done) in g:
            continue
        if (target, RDF.type, NEMIK.Workstream) in g:
            blocker = _repo(target)
            named = None
        elif (target, RDF.type, OSLC_CM.ChangeRequest) in g or (target, RDF.type, NEMIK.Dropped) in g:
            blocker = _repo(target)
            named = target
        else:
            continue  # the operator, or a target outside the graph
        if blocker == _repo(node):
            continue
        claims = {
            w for w in g.subjects(NEMIK.enables, node) if _repo(w) == blocker
        } | {w for w in g.subjects(PROV.wasInformedBy, node) if _repo(w) == blocker}
        if named is not None:
            claims.add(named)
        out.append({
            "blocked": ref(node),
            "title": str(g.value(node, DCTERMS.title) or ""),
            "blocked_on": sorted(str(o) for o in g.objects(node, NEMIK.blockedOn)),
            "blocker": blocker,
            "claimed_by": sorted(ref(c) for c in claims),
        })
    return sorted(out, key=lambda b: (b["blocker"], b["blocked"], b["claimed_by"]))


def annotate(g: Graph) -> None:
    """Mark unclaimed blocks, operator blocks by category, and blocks that resolve to no party."""
    from rdflib import Literal

    # A blocked waypoint whose blocked_on names nothing nemik can resolve (no workstream, waypoint
    # or operator) draws no edge at all; the operator ruled that a defect (2026-09-26).
    for node in g.subjects(OSLC_CM.state, NEMIK.Blocked):
        human = str(g.value(node, NEMIK.blockedKind) or "") == "human"  # drawn to an operator lane
        if (node, NEMIK.waitsFor, None) not in g and not human:
            for text in g.objects(node, NEMIK.blockedOn):
                # nemik:W183: cal:<label>/<uid> is a condition, an event on the operator's calendar
                # (nemik-days resolves it host-side). Checked by form only: the check runs where the
                # calendars are not, and must never read them (nemik:W161).
                if not CAL_BLOCK.fullmatch(str(text).strip()):
                    g.add((node, NEMIK.unresolvedBlocker, text))

    # A peer block that lands on an UMBRELLA -- a waypoint its own repo's open children enable --
    # rather than on the child step doing the work (nemik:W41, luthen-observability's finding):
    # every child then inherits the waiter's weight in nemik-rank, and the umbrella itself can
    # never be the thing that lands.
    for node, _, target in g.triples((None, NEMIK.waitsFor, None)):
        if _repo(target) == _repo(node) or (node, OSLC_CM.state, NEMIK.Done) in g:
            continue
        # nemik:W144: an umbrella splits into two or more open children. A target with exactly one
        # open child is a step in a chain (mtools:W300 <- W299; W310 <- W309): citing it is right,
        # and the work beneath it is reached through it.
        kids = [c for c in g.subjects(NEMIK.enables, target)
                if _repo(c) == _repo(target) and (c, OSLC_CM.state, NEMIK.Done) not in g]
        if len(kids) >= 2:
            g.add((node, NEMIK.umbrellaBlockOn, target))

    # nemik:W177 (operator 2026-10-01): each repo keeps exactly one `working` card unless every open
    # item is blocked. None while something is ready, or several, is the defect; the workstream
    # node carries the count so the finding reads "--" like the adoption one.
    for ws in set(g.objects(None, NEMIK.workstream)):
        mine = list(g.subjects(NEMIK.workstream, ws))
        working = [n for n in mine if (n, OSLC_CM.state, NEMIK.Working) in g]
        ready = [n for n in mine if (n, OSLC_CM.state, NEMIK.Ready) in g]
        if not working and ready:
            g.add((ws, NEMIK.noActiveCard, Literal(len(ready))))
        elif len(working) > 1:
            g.add((ws, NEMIK.extraActiveCards, Literal(len(working))))

    # A block on a waypoint that has already landed (done, or dropped to residue) is stale: the
    # waiter should have been lifted to ready, or its blocked_on trimmed (nemik:W110, paperkit
    # found 8 such in its own queue, some a day old). All of them landed means mis-stated as blocked.
    for node in set(g.subjects(NEMIK.waitsFor, None)):
        if (node, OSLC_CM.state, NEMIK.Done) in g:
            continue
        landed = [t for t in g.objects(node, NEMIK.waitsFor)
                  if (t, OSLC_CM.state, NEMIK.Done) in g or (t, RDF.type, NEMIK.Dropped) in g]
        for t in landed:
            g.add((node, NEMIK.landedBlocker, t))
        if landed and len(landed) == len(set(g.objects(node, NEMIK.blockedOn))):
            g.add((node, NEMIK.allBlockersLanded, Literal(True)))

    # A blocked_on entry that starts as a symbol and trails prose ("W8 (both rewrite the lock)")
    # draws no edge, so it can never be seen to land (nemik:W110). Prose belongs in evidence.
    for node, _, text in g.triples((None, NEMIK.blockedOn, None)):
        t = str(text).strip()
        if _SYMBOLISH.match(t) and not _CLEAN_SYMBOL.fullmatch(t):
            g.add((node, NEMIK.malformedBlocker, text))

    for a in operator_asks(g):
        repo, _, sym = a["ref"].partition(":")
        g.add((URIRef(f"{BASE}{repo}/{sym}"), NEMIK.operatorAsk, Literal(a["category"])))
    for b in inbound(g):
        if not b["claimed_by"]:
            repo, _, sym = b["blocked"].partition(":")
            g.add((URIRef(f"{BASE}{repo}/{sym}"), NEMIK.unclaimedBlockOn, URIRef(f"{BASE}{b['blocker']}")))


def main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """nemik-inbound [REPO]: what is waiting on REPO (or on everyone), and which waypoint claims it."""
    import argparse
    import json

    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(prog="nemik-inbound", description=(main.__doc__ or "").splitlines()[0])
    ap.add_argument("repo", nargs="?", help="only blocks on this workstream")
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github, or the export layout root")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    blocks = [b for b in inbound(g) if not args.repo or b["blocker"] == args.repo]
    if args.json:
        print(json.dumps(blocks, indent=2))
        return
    for b in blocks:
        claim = ", ".join(b["claimed_by"]) or "UNCLAIMED"
        # UNCLAIMED stays as the column token other repos' ticks read; the hint says whose move it is.
        hint = "" if b["claimed_by"] else f"  -- waiting on you, claim with --enables {b['blocked']}"
        print(f"{b['blocker']:24} <- {b['blocked']:28} {claim:28} {b['title'][:60]}{hint}")


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
EXPLICIT = re.compile(r"^\s*operator\s*:\s*(decide|act)\b", re.I)
# Past-tense forms only: a noun like "ruling" appears in questions about rulings too.
ANSWERED = re.compile(r"\b(ruled|keep holding|approved|go-ahead given|decided)\b", re.I)
CONDITION = re.compile(r"^\s*(event:|a green tree|once\b|when\b|after\b)|\bresume when\b|\bonce the\b", re.I)
DECISION = re.compile(
    r"\b(approv\w*|go\b|go-ahead|choice|choose|decide|decision|which|whether|confirm|restart|act|acts|"
    r"teardown|layout|owns|credential|push|commit)\b|\?", re.I,
)
BARE = re.compile(r"^\s*(the\s+)?(operator|user|mikemol|mike|human)\s*(\(\w+\))?\s*$", re.I)

CATEGORIES = ("needs-you", "answered", "condition", "unstated")


def operator_category(text: str) -> str:
    if EXPLICIT.match(text):
        return "needs-you"
    if ANSWERED.search(text):
        return "answered"
    if CONDITION.search(text):
        return "condition"
    if BARE.match(text):
        return "unstated"
    rest = re.sub(r"^\s*(operator|user|mikemol|mike|human)\s*[:(]?", "", text, flags=re.I)
    # nemik:W27: deliberately asymmetric, not a length proxy for "has a real ask". A short
    # scrap with no decide/act keyword is genuinely ambiguous -- unstated. But several words of
    # free text, even with no decide/act verb, is read as needs-you rather than unstated: an
    # agent that bothered to write a sentence almost always wants something, and undercounting
    # here means a real ask silently drops off the operator's radar, which is worse than an
    # occasional over-alert. Only a truly bare blocked_on (BARE, above) reliably lands unstated.
    return "needs-you" if DECISION.search(rest) or len(rest.split()) >= 3 else "unstated"


def _ask_key(text: str) -> str:
    """Normalise an ask so the same decision asked from several repos groups together."""
    t = re.sub(r"^\s*(operator|user|mikemol|mike)\s*[:(]?\s*", "", text, flags=re.I).lower()
    t = re.sub(r"\b(for|of|the|a|an|to)\b|[^a-z0-9 ]", " ", t)
    return " ".join(w for w in t.split() if w not in {"s", "approval", "approve"})[:40]


def waiting_behind(g: Graph, node: URIRef) -> set[URIRef]:
    """Every open waypoint, in any workstream, that waits on `node` directly or through others:
    it waits for it (blocked_on) or `node` enables it. So an operator ask held by one repo shows
    the work queued behind it in others (resumes:W1 behind life:W21, 2026-09-28)."""
    seen: set[URIRef] = set()
    stack = [node]
    while stack:
        n = stack.pop()
        for w in set(g.subjects(NEMIK.waitsFor, n)) | set(g.objects(n, NEMIK.enables)):
            if w not in seen and w != node and (w, OSLC_CM.state, None) in g \
                    and (w, OSLC_CM.state, NEMIK.Done) not in g:
                seen.add(w)
                stack.append(w)
    return seen


def operator_asks(g: Graph) -> list[dict]:
    """Every open waypoint waiting on the operator, categorised, with duplicate asks grouped."""
    from nemik.adapter import OPERATOR

    last: dict[URIRef, str] = {}
    for act in g.subjects(RDF.type, PROV.Activity):
        stamp = str(g.value(act, PROV.startedAtTime) or "")
        for wp in g.objects(act, PROV.used):
            last[wp] = max(last.get(wp, ""), stamp)
    out = []
    # On the operator: resolved to them, or declared blocked_kind human (e.g. "event: ...", "a
    # GREEN tree - operator RULED ...", which name a condition but were filed against the human).
    human = set(g.subjects(NEMIK.waitsFor, OPERATOR)) | {
        n for n in g.subjects(NEMIK.blockedKind, None)
        if str(g.value(n, NEMIK.blockedKind)) == "human" and (n, OSLC_CM.state, NEMIK.Blocked) in g
    }
    repos = {str(w).removeprefix(BASE) for w in g.subjects(RDF.type, NEMIK.Workstream)}
    for node in human:
        if (node, OSLC_CM.state, NEMIK.Done) in g:
            continue
        texts = sorted(str(o) for o in g.objects(node, NEMIK.blockedOn))
        title = str(g.value(node, DCTERMS.title) or "")
        # A bare "operator" with the ask carried in a title that starts "OPERATOR: ..." (summit's
        # convention) states the ask there; read it rather than calling the block unstated.
        if all(BARE.match(t) for t in texts) and re.match(r"^\s*operator\b[^:]{0,60}:", title, re.I):
            texts = [title]
        text = " | ".join(texts)
        cats = [operator_category(t) for t in texts] or ["unstated"]
        # the most actionable reading wins across several blocked_on values
        cat = next(c for c in ("needs-you", "unstated", "condition", "answered") if c in cats)
        out.append({
            "ref": ref(node),
            "title": str(g.value(node, DCTERMS.title) or ""),
            "ask": text,
            "category": cat,
            "ticks_blocked": int(g.value(node, NEMIK.ticksBlocked) or 0),
            "last_activity": last.get(node, ""),
            "key": _ask_key(text) if cat == "needs-you" else "",
            "waiting": sorted(ref(w) for w in waiting_behind(g, node)),
            "dtstart": str(g.value(node, NEMIK.dtstart) or ""),
            "due": str(g.value(node, NEMIK.due) or ""),
            "alarms": sorted(str(a) for a in g.objects(node, NEMIK.alarm)),
            "rrule": str(g.value(node, NEMIK.rrule) or ""),
            "exdates": sorted(str(x) for x in g.objects(node, NEMIK.exdate)),
        })
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
    return sorted(out, key=lambda a: (order[a["category"]], -a["ticks_blocked"], a["ref"]))


def operator_main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """nemik-operator: blocks on the operator, sorted into needs-you / answered / condition / unstated."""
    import argparse
    import json

    from nemik.adapter import ledger_graph
    from nemik.check import LEDGER, default_root, survey, workstream_files

    ap = argparse.ArgumentParser(prog="nemik-operator", description=(operator_main.__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github, or the export layout root")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if g is None:
        g = Graph()
        for _, qg, _ in survey(root):
            if qg is not None:
                g += qg
        for repo, path in workstream_files(root, LEDGER):
            g += ledger_graph(repo, path)[0]
    asks = operator_asks(g)
    if args.json:
        print(json.dumps(asks, indent=2))
        return
    for cat in CATEGORIES:
        rows = [a for a in asks if a["category"] == cat]
        print(f"\n{cat} ({len(rows)})")
        for a in rows:
            dup = f"  same ask as {', '.join(a['same_ask'])}" if a["same_ask"] else ""
            behind = f"  <- {', '.join(a['waiting'])}" if a["waiting"] else ""
            print(f"  {a['ref']:28} {a['ask'][:70]}{dup}{behind}")
