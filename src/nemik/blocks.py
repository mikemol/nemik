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

from rdflib import RDF, Graph, URIRef
from rdflib.namespace import DCTERMS, PROV

from nemik.adapter import BASE, NEMIK, OSLC_CM


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
            "blocked_on": [str(o) for o in g.objects(node, NEMIK.blockedOn)],
            "blocker": blocker,
            "claimed_by": sorted(ref(c) for c in claims),
        })
    return sorted(out, key=lambda b: (b["blocker"], b["blocked"]))


def annotate(g: Graph) -> None:
    """Mark each unclaimed block, and each operator block by category, so the shapes can report them."""
    from rdflib import Literal

    for a in operator_asks(g):
        repo, _, sym = a["ref"].partition(":")
        g.add((URIRef(f"{BASE}{repo}/{sym}"), NEMIK.operatorAsk, Literal(a["category"])))
    for b in inbound(g):
        if not b["claimed_by"]:
            repo, _, sym = b["blocked"].partition(":")
            g.add((URIRef(f"{BASE}{repo}/{sym}"), NEMIK.unclaimedBlockOn, URIRef(f"{BASE}{b['blocker']}")))


def main() -> None:
    """nemik-inbound [REPO]: what is waiting on REPO (or on everyone), and which waypoint claims it."""
    import argparse
    import json

    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(prog="nemik-inbound", description=(main.__doc__ or "").splitlines()[0])
    ap.add_argument("repo", nargs="?", help="only blocks on this workstream")
    ap.add_argument("--root", default=default_root())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
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
        print(f"{b['blocker']:24} <- {b['blocked']:28} {claim:28} {b['title'][:60]}")


# ---- Blocks on the operator -------------------------------------------------------------------
#
# Most blocks that reach the operator are not requests for the operator: the answer is already
# recorded, the wait is really on a condition, or the same decision is asked from several places.
# These rules read the blocked_on text agents actually write (measured 2026-09-26, 29 blocks) and
# sort each block into one category. They are a stated reading, not a verdict: the fix for an
# "unstated" block is for its agent to state the ask.

ANSWERED = re.compile(r"\b(ruled|ruling|keep holding|approved|go-ahead given|decided)\b", re.I)
CONDITION = re.compile(r"^\s*(event:|a green tree|once\b|when\b|after\b)|\bresume when\b|\bonce the\b", re.I)
DECISION = re.compile(
    r"\b(approv\w*|go\b|go-ahead|choice|choose|decide|decision|which|whether|confirm|restart|act|acts|"
    r"teardown|layout|owns|credential|push|commit)\b|\?", re.I,
)
BARE = re.compile(r"^\s*(the\s+)?(operator|user|mikemol|mike|human)\s*(\(\w+\))?\s*$", re.I)

CATEGORIES = ("needs-you", "answered", "condition", "unstated")


def operator_category(text: str) -> str:
    if ANSWERED.search(text):
        return "answered"
    if CONDITION.search(text):
        return "condition"
    if BARE.match(text):
        return "unstated"
    rest = re.sub(r"^\s*(operator|user|mikemol|mike|human)\s*[:(]?", "", text, flags=re.I)
    return "needs-you" if DECISION.search(rest) or len(rest.split()) >= 3 else "unstated"


def _ask_key(text: str) -> str:
    """Normalise an ask so the same decision asked from several repos groups together."""
    t = re.sub(r"^\s*(operator|user|mikemol|mike)\s*[:(]?\s*", "", text, flags=re.I).lower()
    t = re.sub(r"\b(for|of|the|a|an|to)\b|[^a-z0-9 ]", " ", t)
    return " ".join(w for w in t.split() if w not in {"s", "approval", "approve"})[:40]


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
        texts = [str(o) for o in g.objects(node, NEMIK.blockedOn)]
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


def operator_main() -> None:
    """nemik-operator: blocks on the operator, sorted into needs-you / answered / condition / unstated."""
    import argparse
    import json

    from nemik.adapter import ledger_graph
    from nemik.check import LEDGER, default_root, survey, workstream_files

    ap = argparse.ArgumentParser(prog="nemik-operator", description=(operator_main.__doc__ or "").splitlines()[0])
    ap.add_argument("--root", default=default_root())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    from pathlib import Path

    root = Path(args.root)
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
            print(f"  {a['ref']:28} {a['ask'][:70]}{dup}")
