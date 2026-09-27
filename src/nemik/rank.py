"""Cross-repo downstream weight for ranking a queue's ready items (nemik:W34).

mtools' own ordering (mtools:W51 `model.leverage`) counts one queue's immediate edges. This module
adds the layer only nemik can see: the transitive closure across every workstream, with each
downstream waypoint weighted by `data/rank-weights.toml`.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib.resources import files

from rdflib import Graph, URIRef

from nemik.adapter import BASE, NEMIK, OSLC_CM


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
