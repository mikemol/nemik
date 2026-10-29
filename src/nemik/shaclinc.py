# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W400: validate only what a change touches, and keep every other node's findings.

A rebuild validated the whole fleet (the largest phase left once the parse and solve caches landed).
Keyed by the caller (one survey root), the last run's triples and its findings per focus node are
kept. The next run diffs the triples; a node is re-validated when a triple about it changed, or when
it points at a node that did (a shape such as "blocked_on names a landed waypoint" reads its
target's state, one hop). Every other node keeps its findings. Those nodes and their neighbours make
a small graph that is validated whole, so shape targets select exactly as in a full run.

The claim, incremental == full, holds while the neighbourhood is as deep as the deepest shape reads
(nemik.shapedepth derives that from the shapes; unbounded means a full run); tests/test_shaclinc.py
and tests/test_warm_equals_cold.py pin it by comparing against a full run after edits, so a shape
that breaks the claim fails there instead of going stale silently.
"""

from __future__ import annotations

import re

from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import SH
from rdflib.term import Node, URIRef

from nemik.shapedepth import UNBOUNDED, predicates, radius

Result = tuple[str, str]  # (severity IRI, message)

Held = dict[str, tuple[frozenset[tuple[Node, Node, Node]], dict[Node, list[Result]]]]
_LAST: Held = {}
HUB = 40  # a node with more neighbours than this (a workstream) is judged, not walked through


def export_cache() -> Held:
    """nemik:W518: the last runs, for a publisher to keep between its short-lived processes."""
    return dict(_LAST)


def import_cache(held: Held) -> None:
    """nemik:W518: restore runs a publisher kept, so only what changed since is validated again.

    The next findings() diffs against them (a graph with blank nodes would revalidate every one of
    them).
    """
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


def _adjacency(
    now: frozenset[tuple[Node, Node, Node]], touched: set[Node], subjects: set[Node]
) -> dict[Node, set[Node]]:
    """Index which nodes sit either side of an edge.

    Args:
        now: The graph's triples.
        touched: The nodes a change touched.
        subjects: The nodes that are cards (a vocabulary term is only ever an object).

    Returns:
        The neighbours of each node. A dropped card is no longer a subject, but the edges that
        still point at it are its neighbours, so a touched node counts as one.

    """
    adjacent: dict[Node, set[Node]] = {}
    for s, _, o in now:
        if o in subjects or o in touched:
            adjacent.setdefault(s, set()).add(o)
            adjacent.setdefault(o, set()).add(s)
    return adjacent


def _neighbourhood(
    adjacent: dict[Node, set[Node]], seeds: set[Node], hops: int
) -> set[Node]:
    """Grow the seeds by the cards that can read them, in both directions, `hops` deep.

    A shape judges a card from its neighbours' state, and the neighbours can sit either side of an
    edge: ReadyUmbrellaShape reads the kids that enable the umbrella, UmbrellaBlockShape reads the
    umbrella's kids through the waiter's edge. A change to a kid must re-judge both. A hub (a
    workstream joins every card of its repo) is re-judged when reached but not walked through, or
    one changed card would re-judge the repo and, a hop on, the fleet.

    Args:
        adjacent: The neighbours of each node.
        seeds: The nodes to grow from.
        hops: How many undirected edges to follow.

    Returns:
        The seeds and everything within `hops` edges of them, hubs reached but not passed.

    """
    focus = set(seeds)
    front = set(seeds)
    for _ in range(hops):
        reached = {
            n
            for f in front
            if len(adjacent.get(f, ())) <= HUB
            for n in adjacent.get(f, ())
        }
        front = reached - focus
        focus |= reached
    return focus


def _tail(term: str) -> str:
    """Name an IRI or prefixed term by its last segment.

    Args:
        term: An IRI, possibly in angle brackets, or a prefixed name.

    Returns:
        The text after its last #, / or :.

    """
    return re.split(r"[#/:]", term.strip("<>"))[-1]


def watched_predicates(shapes: Graph, texts: list[str]) -> frozenset[str]:
    """Name the predicates a verdict can depend on (nemik:W637).

    A changed triple whose predicate no shape mentions cannot change any verdict, so it should not
    re-judge anything: on the real fleet 5131 of 5208 changes between two runs were queuePosition,
    which no shape reads, and they touched 2570 cards, so every run validated the whole graph.

    Args:
        shapes: The shapes graph.
        texts: Its sh:sparql constraints' query texts.

    Returns:
        The last segments of every IRI the shapes mention and every predicate a query names,
        with "type" (SPARQL's `a`); "?" is in the set when a query's predicate is a variable or
        its text cannot be read, which means every predicate counts.

    """
    names = {"type"}
    for triple in shapes:
        names |= {_tail(str(t)) for t in triple if isinstance(t, URIRef)}
    for text in texts:
        names |= {"?" if p == "?" else _tail(p) for p in predicates(text)}
    return frozenset(names)


def findings(key: str, data: Graph, shapes: Graph) -> list[tuple[Node, str, str]]:
    """(focus, severity IRI, message) for every result, re-validating only what changed.

    Changed means since `key`'s last run: everything on the first, and always when the shapes'
    depth cannot be bounded.
    """
    now = frozenset(data)
    last = _LAST.get(key)
    texts = sorted(str(t) for t in shapes.objects(None, SH.select))
    hops = radius(texts)  # nemik:W626: derived from the shapes
    if last is None or hops == UNBOUNDED:
        by_focus = _results(data, shapes)
    else:
        before, by_focus = last[0], dict(last[1])
        watched = watched_predicates(shapes, texts)
        changed = {
            t for t in before ^ now if "?" in watched or _tail(str(t[1])) in watched
        }
        # A node is a card (or any described thing) when it is a subject; a vocabulary term such as
        # nemik:Done is only ever an object, and following it back would reach every card in that
        # state.
        subjects = {s for s, _, _ in now}
        touched = {s for s, _, _ in changed} | {
            o for _, _, o in changed if o in subjects
        }
        adjacent = _adjacency(now, touched, subjects)
        focus = _neighbourhood(adjacent, touched, hops)
        for n in focus:
            by_focus.pop(n, None)
        live = focus & subjects
        if live:
            # Not pyshacl's focus_nodes: it applies every shape to a named node whatever the shape
            # targets. The focus nodes' own triples and their neighbours' make a subgraph validated
            # whole, so targets select exactly as in a full run; only the focus nodes' results are
            # kept. A hub judged here (a workstream) is judged against ALL its neighbours, or a
            # shape over the whole repo ("no working card") would see only part of it.
            near = _neighbourhood(adjacent, live, hops)
            for hub in live:
                if len(adjacent.get(hub, ())) > HUB:
                    near |= adjacent[hub]
            sub = Graph()
            for t in now:
                if t[0] in near:
                    sub.add(t)
            for f, rows in _results(sub, shapes).items():
                if f in live:
                    by_focus[f] = rows
    _LAST[key] = (now, by_focus)
    return [(f, s, m) for f, rows in by_focus.items() for s, m in rows]
