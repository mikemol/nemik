# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W618: a forecast is open children over the close rate; a bare working card is flagged."""

from rdflib import RDF, Graph
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, waypoint_uri, workstream_uri
from nemik.forecast import days_left, summary

RATE = 2.0  # cards closed per day
FOUR = 4


def _card(g: Graph, symbol: str, state: Node) -> Node:
    """Add a card in a state to repo r.

    Args:
        g: The graph to add to.
        symbol: The card's symbol.
        state: Its OSLC state.

    Returns:
        The card's node.

    """
    node = waypoint_uri("r", symbol)
    g.add((node, RDF.type, OSLC_CM.ChangeRequest))
    g.add((node, OSLC_CM.state, state))
    g.add((node, NEMIK.workstream, workstream_uri("r")))
    return node


def test_days_left_divides_children_by_the_rate() -> None:
    """Four children at two a day is two days; no closures means no forecast."""
    assert days_left(FOUR, RATE) == RATE
    assert days_left(FOUR, 0.0) is None


def test_the_slowest_umbrella_and_the_bare_working_cards_are_summarized() -> None:
    """W1 has four open children (two days); W9 is working with no children at all."""
    g = Graph()
    top = _card(g, "W1", NEMIK.Ready)
    for i in range(2, 6):
        g.add((_card(g, f"W{i}", NEMIK.Ready), NEMIK.enables, top))
    _card(g, "W9", NEMIK.Working)
    slowest, bare = summary(g, "r", RATE)
    assert slowest == RATE
    assert bare == 1


def test_a_working_card_with_children_is_not_bare() -> None:
    """A working card that has an open child can be forecast, so it is not counted."""
    g = Graph()
    top = _card(g, "W1", NEMIK.Working)
    g.add((_card(g, "W2", NEMIK.Ready), NEMIK.enables, top))
    assert summary(g, "r", RATE) == (None, 0)
