"""Cross-repo downstream weight for ranking a queue's ready items (nemik:W34).

mtools' own ordering (mtools:W51 `model.leverage`) counts one queue's immediate edges. This module
adds the layer only nemik can see: the transitive closure across every workstream, with each
downstream waypoint weighted by `data/rank-weights.toml`.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from importlib.resources import files

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS

from nemik.adapter import BASE, NEMIK, OSLC_CM, workstream_uri


@dataclass(frozen=True)
class Weights:
    local: int
    peer: int
    peer_blocked: int


def load_weights(text: str | None = None) -> Weights:
    """Read the edge weights; `text` overrides the packaged file (for tests)."""
    if text is None:
        text = files("nemik.data").joinpath("rank-weights.toml").read_text()
    data = tomllib.loads(text)
    return Weights(local=int(data["local"]), peer=int(data["peer"]), peer_blocked=int(data["peer_blocked"]))


def _repo(node: URIRef) -> str:
    return str(node).removeprefix(BASE).partition("/")[0]


def successors(g: Graph, node: URIRef) -> set[URIRef]:
    """What this waypoint moves: what it `enables`, and every waypoint that `waitsFor` it."""
    return set(g.objects(node, NEMIK.enables)) | set(g.subjects(NEMIK.waitsFor, node))


def downstream_weight(g: Graph, node: URIRef, weights: Weights) -> int:
    """Sum of weights over the transitive downstream closure of `node`, each waypoint counted once.

    ⚑ A `done` waypoint contributes nothing and is not traversed through: finished work is not
    waiting on anything. A cycle terminates on the visited set; `node` itself never counts.
    """
    origin = _repo(node)
    seen: set[URIRef] = {node}
    stack = [node]
    total = 0
    while stack:
        for nxt in successors(g, stack.pop()):
            if nxt in seen or (nxt, OSLC_CM.state, NEMIK.Done) in g:
                continue
            seen.add(nxt)
            stack.append(nxt)
            if _repo(nxt) == origin:
                total += weights.local
            elif (nxt, OSLC_CM.state, NEMIK.Blocked) in g:
                total += weights.peer_blocked
            else:
                total += weights.peer
    return total


def _open(g: Graph, n: URIRef) -> bool:
    return (n, OSLC_CM.state, NEMIK.Done) not in g and (n, OSLC_CM.state, None) in g


def frontier(g: Graph, goal: URIRef) -> tuple[set[URIRef], set[str]]:
    """(dG, ddG) for a goal (nemik:W71, W73).

    dG: the open leaves under `goal` within its repo, found by walking back through what enables
    it and what it waits on. A leaf is an open waypoint that nothing open in the repo feeds. The
    goal is its own frontier when nothing feeds it.
    ddG: what those leaves wait on from outside the repo. That is each leaf's blocked_on entries
    that are not local symbols, plus open enablers from another repo. The path to `goal` is clear
    exactly when ddG is empty: every remaining obstacle is work this repo can do itself.
    """
    repo = _repo(goal)
    seen, stack, leaves, outside = {goal}, [goal], set(), set()
    while stack:
        n = stack.pop()
        feeders = set(g.subjects(NEMIK.enables, n)) | {
            t for t in g.objects(n, NEMIK.waitsFor) if str(t).startswith(BASE) and "/" in str(t)[len(BASE):]}
        local_open = set()
        for f in feeders:
            if not _open(g, f):
                continue
            if _repo(f) == repo:
                local_open.add(f)
            else:
                outside.add(ref_of(f))
        if not local_open:
            leaves.add(n)
            for lit in g.objects(n, NEMIK.blockedOn):
                if not re.fullmatch(r"W\d+", str(lit).strip()):
                    outside.add(str(lit))
        for f in local_open - seen:
            seen.add(f)
            stack.append(f)
    return leaves, outside


def ref_of(node: URIRef) -> str:
    r, _, sym = str(node).removeprefix(BASE).partition("/")
    return f"{r}:{sym}"


def is_umbrella(g: Graph, n: URIRef) -> bool:
    """A ready item with open work under it (nemik:W74): its frontier is not itself, so it is not a leaf."""
    return frontier(g, n)[0] != {n}


def umbrellas(g: Graph, repo: str) -> list[URIRef]:
    ws = workstream_uri(repo)
    return [n for n in g.subjects(NEMIK.workstream, ws)
            if (n, OSLC_CM.state, NEMIK.Ready) in g and is_umbrella(g, n)]


def rank(g: Graph, repo: str, weights: Weights) -> list[dict]:
    """Every ready leaf in `repo`, highest cross-repo downstream weight first (lower symbol on ties).

    Umbrellas are left out: their open children are what can be worked (nemik:W74).
    """
    ws = workstream_uri(repo)
    ready = [n for n in g.subjects(NEMIK.workstream, ws)
             if (n, OSLC_CM.state, NEMIK.Ready) in g and not is_umbrella(g, n)]
    rows = [{
        "symbol": str(g.value(n, NEMIK.symbol)),
        "weight": downstream_weight(g, n, weights),
        "title": str(g.value(n, DCTERMS.title) or ""),
    } for n in ready]
    return sorted(rows, key=lambda r: (-r["weight"], int(r["symbol"].lstrip("W"))))


def main() -> None:
    """nemik-rank REPO: REPO's ready waypoints ordered by cross-repo downstream weight."""
    import argparse
    import json
    from pathlib import Path

    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(prog="nemik-rank", description=(main.__doc__ or "").splitlines()[0])
    ap.add_argument("repo", help="the workstream whose ready items to rank")
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github, or the export layout root")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the ready item mtools works next is outweighed by another (drift witness)")
    args = ap.parse_args()
    g = Graph()
    for _, qg, _ in survey(args.root):
        if qg is not None:
            g += qg
    weights = load_weights()
    if args.check:
        ums = umbrellas(g, args.repo)
        for u in ums:
            print(f"rank: UMBRELLA {ref_of(u)} is ready with open work under it: "
                  + ", ".join(sorted(ref_of(x) for x in frontier(g, u)[0])))
        d = drift(g, args.repo, weights)
        if d is None:
            if ums:
                raise SystemExit(1)
            print(f"rank: OK {args.repo}: next ready item carries the top cross-repo weight")
            raise SystemExit(0)
        nxt, top = d
        print(f"rank: DRIFT {args.repo}: next is {nxt['symbol']} ({nxt['weight']}) "
              f"but {top['symbol']} carries {top['weight']}")
        raise SystemExit(1)
    rows = rank(g, args.repo, weights)
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    for r in rows:
        print(f"{r['symbol']:6} {r['weight']:4}  {r['title'][:80]}")


def drift(g: Graph, repo: str, weights: Weights) -> tuple[dict, dict] | None:
    """(next, heavier) when the ready item mtools puts first is outweighed by another ready item.

    ⚑ "Next" is mtools' own order (`nemik:queuePosition`, from `model.ordered`), not this
    module's: the witness compares what the session WILL work against what nemik-rank says it
    should, so it fails exactly when the two disagree on the top item.
    """
    rows = rank(g, repo, weights)
    if not rows:
        return None
    ws = workstream_uri(repo)
    pos = {str(g.value(n, NEMIK.symbol)): int(g.value(n, NEMIK.queuePosition))
           for n in g.subjects(NEMIK.workstream, ws) if g.value(n, NEMIK.queuePosition) is not None}
    nxt = min(rows, key=lambda r: pos.get(r["symbol"], 1 << 30))
    return (nxt, rows[0]) if rows[0]["weight"] > nxt["weight"] else None
