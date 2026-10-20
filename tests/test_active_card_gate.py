# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W633: a card that a queued or gating commit stack names counts as working."""

from rdflib import Graph, Literal
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri, workstream_uri
from nemik.blocks import annotate
from nemik.check import shapes
from nemik.shaclinc import findings


def _repo(g: Graph, *, gating: tuple[str, ...]) -> Node:
    """Add a repo of two ready cards, with the named ones marked as in the commit gate.

    Args:
        g: The graph to add to.
        gating: The symbols a commit stack names.

    Returns:
        The repo's workstream node.

    """
    ws = workstream_uri("a")
    for symbol in ("W1", "W2"):
        n = waypoint_uri("a", symbol)
        g.add((n, OSLC_CM.state, STATE["ready"]))
        g.add((n, NEMIK.workstream, ws))
        if symbol in gating:
            g.add((n, NEMIK.inGate, Literal("gate")))
    return ws


def _said(g: Graph, ws: Node, key: str) -> list[str]:
    """Collect what the active-card shape says about a workstream.

    Args:
        g: The graph.
        ws: The workstream node.
        key: A cache key unique to the case.

    Returns:
        The messages naming that workstream.

    """
    annotate(g)
    return [m for focus, _, m in findings(key, g, shapes()) if focus == ws]


def test_ready_cards_and_nothing_in_the_gate_is_asked_for_a_working_card() -> None:
    """No card marked: the ordinary finding."""
    g = Graph()
    ws = _repo(g, gating=())
    assert [m.startswith("no working card") for m in _said(g, ws, "gate-none")] == [
        True
    ]


def test_a_card_in_the_gate_counts_as_the_working_one() -> None:
    """One ready card is in a gating stack: nothing is asked."""
    g = Graph()
    ws = _repo(g, gating=("W1",))
    assert _said(g, ws, "gate-one") == []
