"""nemik:W412: one pass over a graph into plain dicts, read by the hot loops for one build.

A rebuild asked rdflib 3.3 M triple patterns (17 s of 27) for the same few facts per card: its
state, what it enables, what waits for it. Inside `indexed()` the first asker of a graph builds those
maps once and every later asker reads them. Outside the scope nothing is cached, so a caller that
mutates a graph between questions never reads a stale answer; inside it, an entry is checked against
the graph's identity and size, which catches the additions a build makes (assume_done copies).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from rdflib import Graph
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM


@dataclass
class Index:
    """The facts per card that the hot loops ask for."""

    state: dict[Node, set[Node]] = field(default_factory=dict)
    enables: dict[Node, set[Node]] = field(default_factory=dict)
    waited_by: dict[Node, set[Node]] = field(default_factory=dict)
    # a whole-graph answer asked more than once per build (once per repo's health)
    operator_asks: list[dict[str, object]] | None = None

    def successors(self, node: Node) -> set[Node]:
        return self.enables.get(node, set()) | self.waited_by.get(node, set())

    def open(self, node: Node) -> bool:
        s = self.state.get(node, set())
        return bool(s) and NEMIK.Done not in s

    def has_state(self, node: Node, state: Node) -> bool:
        return state in self.state.get(node, ())


_SCOPE: dict[int, tuple[Graph, int, Index]] | None = None


@contextmanager
def indexed() -> Iterator[None]:
    """Keep each graph's index for the duration of the block (one build)."""
    global _SCOPE
    outer, _SCOPE = _SCOPE, {} if _SCOPE is None else _SCOPE
    try:
        yield
    finally:
        _SCOPE = outer


def index(g: Graph) -> Index | None:
    """The graph's index inside `indexed()`, else None (the caller asks the graph)."""
    if _SCOPE is None:
        return None
    hit = _SCOPE.get(id(g))
    if hit is not None and hit[0] is g and hit[1] == len(g):
        return hit[2]
    ix = Index()
    for s, o in g.subject_objects(OSLC_CM.state):
        ix.state.setdefault(s, set()).add(o)
    for s, o in g.subject_objects(NEMIK.enables):
        ix.enables.setdefault(s, set()).add(o)
    for s, o in g.subject_objects(NEMIK.waitsFor):
        ix.waited_by.setdefault(o, set()).add(s)
    _SCOPE[id(g)] = (g, len(g), ix)
    return ix
