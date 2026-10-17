# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W487: an open card with no edge at all is named; one with any edge is not."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph, waypoint_uri
from nemik.check import shapes
from nemik.shaclinc import findings


def _queue(tmp_path: Path, cards: list[dict[str, object]]) -> Graph:
    """Read a queue of the given cards.

    Args:
        tmp_path: A scratch directory.
        cards: The queue's waypoints.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/a",
        "counter": len(cards),
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / "a.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("a", path)


def _card(symbol: str, status: str = "ready", **more: object) -> dict[str, object]:
    """Build a card.

    Args:
        symbol: The card's symbol.
        status: Its status.
        **more: Further fields.

    Returns:
        The card.

    """
    return {"symbol": symbol, "title": symbol, "status": status, **more}


def _orphans(g: Graph) -> set[str]:
    """Collect the symbols OrphanLeafShape names.

    Args:
        g: The queue's graph.

    Returns:
        The symbols of the named cards.

    """
    rows = findings(f"orphan-{id(g)}", g, shapes())
    named = {str(focus) for focus, _, m in rows if "no edge joins" in m}
    return {s for s in ("W1", "W2", "W3", "W4") if str(waypoint_uri("a", s)) in named}


def test_only_the_card_with_no_edge_is_named(tmp_path: Path) -> None:
    """W1 enables W2; W3 stands alone; W4 is done. Only W3 is an orphan leaf."""
    g = _queue(
        tmp_path,
        [_card("W1", enables=["W2"]), _card("W2"), _card("W3"), _card("W4", "done")],
    )
    assert _orphans(g) == {"W3"}
