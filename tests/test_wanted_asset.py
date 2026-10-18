# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W343: a card says what it wants and who else may deliver it, and the graph carries it."""

import json
from pathlib import Path

from rdflib import Graph, Literal

from nemik.adapter import NEMIK, queue_graph, reference_uri, waypoint_uri


def _queue(tmp_path: Path) -> Graph:
    """Read a queue with one card that wants an asset from either of two suppliers.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The queue's graph.

    """
    card: dict[str, object] = {
        "symbol": "W1",
        "title": "waits on a palette",
        "status": "blocked",
        "blocked_on": ["other:W9"],
        "blocked_kind": "agent",
        "acceptable_suppliers": ["other:W9", "third:W4"],
        "want": "a colour-blind-safe palette",
    }
    plain: dict[str, object] = {"symbol": "W2", "title": "plain", "status": "ready"}
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/a",
        "counter": 2,
        "residue": [],
        "waypoints": [card, plain],
    }
    path = tmp_path / "a.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("a", path)


def test_a_card_names_the_suppliers_that_would_do(tmp_path: Path) -> None:
    """Each acceptable supplier is a reference to that card; a bare symbol is local."""
    g = _queue(tmp_path)
    node = waypoint_uri("a", "W1")
    got = set(g.objects(node, NEMIK.acceptableSupplier))
    assert got == {reference_uri("a", "other:W9"), reference_uri("a", "third:W4")}


def test_a_card_says_what_it_wants_in_one_line(tmp_path: Path) -> None:
    """The want is a literal on the waiting card."""
    g = _queue(tmp_path)
    node = waypoint_uri("a", "W1")
    assert g.value(node, NEMIK.wantText) == Literal("a colour-blind-safe palette")


def test_a_card_without_them_carries_neither(tmp_path: Path) -> None:
    """The fields are optional, and a plain card gains no triple."""
    g = _queue(tmp_path)
    node = waypoint_uri("a", "W2")
    assert not list(g.objects(node, NEMIK.acceptableSupplier))
    assert g.value(node, NEMIK.wantText) is None


def test_the_fallback_does_not_change_the_block(tmp_path: Path) -> None:
    """The card still waits on its blocker: a supplier is a fallback, never a second block."""
    g = _queue(tmp_path)
    node = waypoint_uri("a", "W1")
    assert Literal("other:W9") in set(g.objects(node, NEMIK.blockedOn))
