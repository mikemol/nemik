# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W412: one pass over a graph into plain dicts, read by the hot loops for one build.

A rebuild asked rdflib 3.3 M triple patterns (17 s of 27) for the same few facts per card:
its
state, what it enables, what waits for it. Inside `indexed()` the first asker of a graph builds
those maps once and every later asker reads them. Outside the scope nothing is cached, so a caller
that mutates a graph between questions never reads a stale answer; inside it, an entry is checked
against the graph's identity and size, which catches the additions a build makes (assume_done
copies).

nemik:W1842, W1843, W1844: this module no longer imports collections.abc, contextlib or dataclasses,
nor nemik.adapter. The scope is a class with __enter__ and __exit__, the index a plain class, and
the few rdflib terms it asks for are built here from nemik.vocab's strings.
"""

from __future__ import annotations

import weakref

from rdflib import URIRef

from nemik._typing import TYPE_CHECKING
from nemik.vocab import BASE, NEMIK_BASE, OSLC_CM_BASE

if TYPE_CHECKING:
    from rdflib import Graph
    from rdflib.term import Node

    from nemik.blocks import AskRow
    from nemik.cards import Card
    from nemik.score import Weights

STATE = URIRef(OSLC_CM_BASE + "state")
ENABLES = URIRef(NEMIK_BASE + "enables")
WAITS_FOR = URIRef(NEMIK_BASE + "waitsFor")
DONE = URIRef(NEMIK_BASE + "Done")
BLOCKED = URIRef(NEMIK_BASE + "Blocked")


class Index:
    """The facts per card that the hot loops ask for."""

    state: dict[Node, set[Node]]
    enables: dict[Node, set[Node]]
    waited_by: dict[Node, set[Node]]
    # a whole-graph answer asked more than once per build (once per repo's health)
    operator_asks: list[AskRow] | None
    # nemik:W518: every card as plain data, read from the graph once (health and critical asked
    # for it 31 times in one build, 10 s of a warm publish)
    cards: dict[str, Card] | None

    def __init__(self) -> None:
        """Start with no facts, no operator asks and no cards read."""
        self.state = {}
        self.enables = {}
        self.waited_by = {}
        self.operator_asks = None
        self.cards = None

    def successors(self, node: Node) -> set[Node]:
        """Find the cards that wait on this one.

        Returns:
            The cards it enables and the cards blocked on it.

        """
        return self.enables.get(node, set()) | self.waited_by.get(node, set())

    def open(self, node: Node) -> bool:
        """Judge whether a card is open.

        Returns:
            True when the card has a state and is not done.

        """
        s = self.state.get(node, set())
        return bool(s) and DONE not in s

    def has_state(self, node: Node, state: Node) -> bool:
        """Judge whether a card is in a state.

        Returns:
            True when the card carries the state.

        """
        return state in self.state.get(node, ())


_SCOPE: list[dict[int, tuple[weakref.ref[Graph], int, Index]] | None] = [None]


class Scope:
    """Keep each graph's index for the duration of a block (one build): `with indexed():`."""

    outer: dict[int, tuple[weakref.ref[Graph], int, Index]] | None

    def __init__(self) -> None:
        """Start with no enclosing scope remembered."""
        self.outer = None

    def __enter__(self) -> None:
        """Open the scope, or join the one already open."""
        self.outer = _SCOPE[0]
        _SCOPE[0] = {} if self.outer is None else self.outer

    def __exit__(self, kind: object, error: object, trace: object) -> None:
        """Close the scope, restoring the enclosing one (or none)."""
        _SCOPE[0] = self.outer


indexed = Scope


def index(g: Graph) -> Index | None:
    """Give the graph's index inside `indexed()`, else None (the caller asks the graph).

    Returns:
        The graph's index inside an `indexed()` scope, built on first use and built
        again when the graph's size changed; None outside a scope.

    """
    scope = _SCOPE[0]
    if scope is None:
        return None
    hit = scope.get(id(g))
    if hit is not None and hit[0]() is g and hit[1] == len(g):
        return hit[2]
    ix = Index()
    for s, o in g.subject_objects(STATE):
        ix.state.setdefault(s, set()).add(o)
    for s, o in g.subject_objects(ENABLES):
        ix.enables.setdefault(s, set()).add(o)
    for s, o in g.subject_objects(WAITS_FOR):
        ix.waited_by.setdefault(o, set()).add(s)
    key = id(g)

    def forget(dead: weakref.ref[Graph]) -> None:
        # nemik:W518: the entry goes with its graph. A strong reference kept every copy a build made
        # (one per repo) alive to the end of the scope: +140 MB at the peak of a publish.
        if key in scope and scope[key][0] is dead:
            del scope[key]

    scope[key] = (weakref.ref(g, forget), len(g), ix)
    return ix


def repo_of(node: Node) -> str:
    """Name the workstream a waypoint belongs to.

    Returns:
        The repo segment of the node's IRI.

    """
    return str(node).removeprefix(BASE).partition("/")[0]


def successors(g: Graph, node: Node) -> set[Node]:
    """Give what this waypoint moves: what it `enables`, and every waypoint that `waitsFor` it.

    Returns:
        The waypoints it enables and those that wait for it.

    """
    ix = index(g)
    if ix is not None:
        return ix.successors(node)
    return set(g.objects(node, ENABLES)) | set(g.subjects(WAITS_FOR, node))


def downstream_weight(g: Graph, node: Node, weights: Weights) -> int:
    """Sum of weights over the transitive downstream closure of `node`, each waypoint counted once.

    ⚑ A `done` waypoint contributes nothing and is not traversed through: finished work is not
    waiting on anything. A cycle terminates on the visited set; `node` itself never counts.

    Returns:
        The total weight: `local` for each successor in the node's repo,
        `peer_blocked` for a blocked one elsewhere, else `peer`.

    """
    origin = repo_of(node)
    seen: set[Node] = {node}
    stack = [node]
    total = 0
    while stack:
        for nxt in successors(g, stack.pop()):
            if nxt in seen or (nxt, STATE, DONE) in g:
                continue
            seen.add(nxt)
            stack.append(nxt)
            if repo_of(nxt) == origin:
                total += weights.local
            elif (nxt, STATE, BLOCKED) in g:
                total += weights.peer_blocked
            else:
                total += weights.peer
    return total


def open_card(g: Graph, n: Node) -> bool:
    """Say whether a card is not done.

    Returns:
        True when the card has a state and it is not Done.

    """
    ix = index(g)
    if ix is not None:
        return ix.open(n)
    return (n, STATE, DONE) not in g and (n, STATE, None) in g


def ref_of(node: Node) -> str:
    """Name a card node by its citation.

    Returns:
        The card as `<repo>:W<n>`.

    """
    r, _, sym = str(node).removeprefix(BASE).partition("/")
    return f"{r}:{sym}"
