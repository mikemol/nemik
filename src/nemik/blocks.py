"""Cross-workstream blocks, read from both sides.

A waypoint blocked on another workstream is only actionable when both agents can name the same
thing: the blocked agent cites `<repo>:W<n>`, and the blocker knows which of its own waypoints
is the block. `blocked_on` often names only a repo or a session. This module finds, for each such
block, the blocker's waypoint that CLAIMS it, meaning one that `enables` the blocked waypoint
(`repo:W<n>` is legal in enables since mtools 9236d5e) or was `caused_by` it. Blocks with no claim
are the ones nobody can reference yet.
"""

from __future__ import annotations

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
    """Mark each unclaimed block so the shapes can report it."""
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
