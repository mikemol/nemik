# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1083: a ready card a queued or gating commit stack names is being worked, and says so."""

from rdflib import RDF, Graph, Literal
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri, workstream_uri
from nemik.blocks import annotate
from nemik.check import shapes
from nemik.shaclinc import findings

SAYS = "ready, but a queued"


def _card(g: Graph, symbol: str, status: str, *, gating: bool) -> Node:
    """Add one card, optionally named by a queued or gating stack.

    Returns:
        The card's node.

    """
    node = waypoint_uri("a", symbol)
    g.add((node, RDF.type, OSLC_CM.ChangeRequest))
    g.add((node, OSLC_CM.state, STATE[status]))
    g.add((node, NEMIK.workstream, workstream_uri("a")))
    if gating:
        g.add((node, NEMIK.inGate, Literal("gate")))
    return node


def _said(g: Graph, node: Node) -> list[str]:
    """Collect what the shapes say about one card.

    Returns:
        The messages naming that card.

    """
    annotate(g)
    key = f"gating-{id(g)}"
    return [m for focus, _, m in findings(key, g, shapes()) if focus == node]


def test_a_ready_card_a_stack_names_is_flagged() -> None:
    """Ready and gating: it is being worked, the queue should say working."""
    g = Graph()
    node = _card(g, "W1", "ready", gating=True)
    assert len([m for m in _said(g, node) if m.startswith(SAYS)]) == 1


def test_a_working_card_in_the_gate_is_clean() -> None:
    """Marked working while its stack gates: nothing to say."""
    g = Graph()
    node = _card(g, "W1", "working", gating=True)
    assert not any(m.startswith(SAYS) for m in _said(g, node))


def test_a_ready_card_no_stack_names_is_clean() -> None:
    """Ready and idle is an honest mark."""
    g = Graph()
    node = _card(g, "W1", "ready", gating=False)
    assert not any(m.startswith(SAYS) for m in _said(g, node))
