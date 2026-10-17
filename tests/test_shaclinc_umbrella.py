# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W625: a kid's change must re-judge the umbrella and the waiter two hops away."""

from rdflib import RDF, Graph
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, waypoint_uri, workstream_uri
from nemik.blocks import annotate
from nemik.check import shapes
from nemik.shaclinc import findings


def _card(g: Graph, repo: str, symbol: str, state: Node) -> Node:
    """Add a card in a state to a repo.

    Args:
        g: The graph to add to.
        repo: The repo's name.
        symbol: The card's symbol.
        state: Its OSLC state.

    Returns:
        The card's node.

    """
    node = waypoint_uri(repo, symbol)
    g.add((node, RDF.type, OSLC_CM.ChangeRequest))
    g.add((node, OSLC_CM.state, state))
    g.add((node, NEMIK.workstream, workstream_uri(repo)))
    return node


def _world() -> tuple[Graph, Node, Node, Node, Node]:
    """Build an umbrella U with two open kids in repo b, and a waiter in repo a blocked on U.

    Returns:
        The graph, the umbrella, the two kids and the waiter.

    """
    g = Graph()
    top = _card(g, "b", "W1", NEMIK.Ready)
    one = _card(g, "b", "W2", NEMIK.Ready)
    two = _card(g, "b", "W3", NEMIK.Ready)
    waiter = _card(g, "a", "W9", NEMIK.Blocked)
    g.add((one, NEMIK.enables, top))
    g.add((two, NEMIK.enables, top))
    g.add((waiter, NEMIK.waitsFor, top))
    return g, top, one, two, waiter


def _close(g: Graph, node: Node) -> None:
    """Mark a card done.

    Args:
        g: The graph.
        node: The card.

    """
    g.remove((node, OSLC_CM.state, None))
    g.add((node, OSLC_CM.state, NEMIK.Done))


def test_closing_the_kids_changes_the_umbrella_and_the_waiters_verdicts() -> None:
    """After both kids are done the incremental run must equal a full one (no stale umbrella)."""
    g, _, one, two, _ = _world()
    sh = shapes()
    annotate(g)
    findings("umbrella-two-hop", g, sh)
    _close(g, one)
    _close(g, two)
    annotate(g)
    inc = sorted(findings("umbrella-two-hop", g, sh))
    full = sorted(findings("umbrella-two-hop-fresh", g, sh))  # a new key is a full run
    assert inc == full
