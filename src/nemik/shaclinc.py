# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W400: validate only what a change touches, and keep every other node's findings.

A rebuild validated the whole fleet (the largest phase left once the parse and solve caches landed).
Keyed by the caller (one survey root), the last run's triples and its findings per focus node are kept.
The next run diffs the triples; a node is re-validated when a triple about it changed, or when it
points at a node that did (a shape such as "blocked_on names a landed waypoint" reads its target's
state, one hop). Every other node keeps its findings. Those nodes and their neighbours make a small
graph that is validated whole, so shape targets select exactly as in a full run.

The claim, incremental == full, holds for constraints that read at most one hop from the focus, which is
every shape in shapes.ttl today; tests/test_shaclinc.py pins it by comparing against a full run after
edits, so a deeper shape that breaks the claim fails there instead of going stale silently.
"""

from __future__ import annotations

from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import SH
from rdflib.term import Node

Result = tuple[str, str]  # (severity IRI, message)

Held = dict[str, tuple[frozenset[tuple[Node, Node, Node]], dict[Node, list[Result]]]]
_LAST: Held = {}


def export_cache() -> Held:
    """nemik:W518: the last runs, for a publisher to keep between its short-lived processes."""
    return dict(_LAST)


def import_cache(held: Held) -> None:
    """nemik:W518: restore runs a publisher kept: the next findings() diffs against them, so only what
    changed since is validated again (a graph with blank nodes would revalidate every one of them)."""
    _LAST.update(held)


def _results(data: Graph, shapes: Graph) -> dict[Node, list[Result]]:
    from nemik.shaclcache import cached_sparql_parse

    # nemik:W254: pyshacl hands rdflib the same constraint text for every focus node; parse it once.
    with cached_sparql_parse():
        _, report, _ = validate(data, shacl_graph=shapes)
    out: dict[Node, list[Result]] = {}
    for f, sev, msg in report.query(
        "SELECT ?f ?s ?m WHERE { ?r sh:focusNode ?f ; sh:resultSeverity ?s ; sh:resultMessage ?m }",
        initNs={"sh": SH},
    ):
        out.setdefault(f, []).append((str(sev), str(msg)))
    return out


HOPS = 2  # nemik:W625: the deepest chain a shape reads, UmbrellaBlockShape (waiter, umbrella, kids)


def _neighbourhood(
    now: frozenset[tuple[Node, Node, Node]], touched: set[Node], subjects: set[Node]
) -> set[Node]:
    """Grow the touched nodes by the cards that can read them, in both directions, HOPS deep.

    A shape judges a card from its neighbours' state, and the neighbours can sit either side of an
    edge: ReadyUmbrellaShape reads the kids that enable the umbrella, UmbrellaBlockShape reads the
    umbrella's kids through the waiter's edge. A change to a kid must re-judge both.

    Args:
        now: The graph's triples.
        touched: The nodes a change touched.
        subjects: The nodes that are cards (a vocabulary term is only ever an object).

    Returns:
        The touched nodes and everything within HOPS undirected edges of them.

    """
    adjacent: dict[Node, set[Node]] = {}
    for s, _, o in now:
        if o in subjects:
            adjacent.setdefault(s, set()).add(o)
            adjacent.setdefault(o, set()).add(s)
    focus = set(touched)
    for _ in range(HOPS):
        focus |= {n for f in focus for n in adjacent.get(f, ())}
    return focus


def findings(key: str, data: Graph, shapes: Graph) -> list[tuple[Node, str, str]]:
    """(focus, severity IRI, message) for every result, re-validating only what changed since `key`'s
    last run (everything on the first)."""
    now = frozenset(data)
    last = _LAST.get(key)
    if last is None:
        by_focus = _results(data, shapes)
    else:
        before, by_focus = last[0], dict(last[1])
        changed = before ^ now
        # A node is a card (or any described thing) when it is a subject; a vocabulary term such as
        # nemik:Done is only ever an object, and following it back would reach every card in that state.
        subjects = {s for s, _, _ in now}
        touched = {s for s, _, _ in changed} | {
            o for _, _, o in changed if o in subjects
        }
        focus = _neighbourhood(now, touched, subjects)
        for n in focus:
            by_focus.pop(n, None)
        live = focus & subjects
        if live:
            # Not pyshacl's focus_nodes: it applies every shape to a named node whatever the shape
            # targets. The focus nodes' own triples and their neighbours' make a subgraph validated
            # whole, so targets select exactly as in a full run; only the focus nodes' results are kept.
            near = _neighbourhood(now, live, subjects)
            sub = Graph()
            for t in now:
                if t[0] in near:
                    sub.add(t)
            for f, rows in _results(sub, shapes).items():
                if f in live:
                    by_focus[f] = rows
    _LAST[key] = (now, by_focus)
    return [(f, s, m) for f, rows in by_focus.items() for s, m in rows]
