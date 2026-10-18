# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W684: a ready leaf with no manifest is flagged in the graph payload; others are not."""

from rdflib import Graph, Literal

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.blocks import node_marks, ready_unmanifested


def _card(g: Graph, symbol: str, state: str, planned: list[str]) -> None:
    node = waypoint_uri("alpha", symbol)
    g.add((node, OSLC_CM.state, STATE[state]))
    for path in planned:
        g.add((node, NEMIK.plannedPath, Literal(path)))


def test_only_a_ready_leaf_with_no_manifest_is_reported() -> None:
    """W1 is ready and bare; W2 has a manifest; W3 works; W4 is ready but open W5 enables it."""
    g = Graph()
    _card(g, "W1", "ready", [])
    _card(g, "W2", "ready", ["src/a.py"])
    _card(g, "W3", "working", [])
    _card(g, "W4", "ready", [])
    _card(g, "W5", "working", [])
    g.add((waypoint_uri("alpha", "W5"), NEMIK.enables, waypoint_uri("alpha", "W4")))
    assert ready_unmanifested(g) == [waypoint_uri("alpha", "W1")]


def test_an_enabler_that_is_done_no_longer_hides_the_card() -> None:
    """A done card enabling it is not an open prerequisite, so the bare ready card is reported."""
    g = Graph()
    _card(g, "W1", "ready", [])
    _card(g, "W2", "done", [])
    g.add((waypoint_uri("alpha", "W2"), NEMIK.enables, waypoint_uri("alpha", "W1")))
    assert ready_unmanifested(g) == [waypoint_uri("alpha", "W1")]


def test_the_marks_name_each_flag_by_node_id() -> None:
    """A bare leaf gets needs_manifest, a card behind an open one gets behind_open, others none."""
    g = Graph()
    _card(g, "W1", "ready", [])
    _card(g, "W2", "ready", ["src/a.py"])
    _card(g, "W3", "working", [])
    g.add((waypoint_uri("alpha", "W3"), NEMIK.enables, waypoint_uri("alpha", "W2")))
    marks = node_marks(g)
    assert marks == {
        str(waypoint_uri("alpha", "W1")): {"needs_manifest": True},
        str(waypoint_uri("alpha", "W2")): {"behind_open": True},
    }
