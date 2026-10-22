# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W840: a card in the landed status reads without a vocabulary Warning, and stays open."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import OSLC_CM, queue_graph, waypoint_uri
from nemik.check import shapes
from nemik.shaclinc import findings


def _queue(tmp_path: Path, statuses: dict[str, str]) -> Graph:
    """Read a queue with one card per symbol, in the given status.

    Args:
        tmp_path: A scratch directory.
        statuses: {symbol: status}.

    Returns:
        The queue's graph.

    """
    cards: list[dict[str, object]] = [
        {"symbol": symbol, "title": symbol, "status": status}
        for symbol, status in statuses.items()
    ]
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


def _divergent(g: Graph, symbols: list[str]) -> set[str]:
    """Collect the symbols the state vocabulary Warning names.

    Args:
        g: The queue's graph.
        symbols: The symbols to look for.

    Returns:
        Those the Warning names.

    """
    rows = findings(f"landed-{id(g)}", g, shapes())
    named = {str(focus) for focus, _, m in rows if "status outside" in m}
    return {s for s in symbols if str(waypoint_uri("a", s)) in named}


def test_landed_is_accepted_and_an_unknown_status_still_warns(tmp_path: Path) -> None:
    """The five statuses read clean; a sixth the vocabulary does not know is named."""
    statuses = {
        "W1": "ready",
        "W2": "working",
        "W3": "blocked",
        "W4": "landed",
        "W5": "done",
        "W6": "parked",
    }
    g = _queue(tmp_path, statuses)
    assert _divergent(g, list(statuses)) == {"W6"}


def test_a_landed_card_is_open_not_closed(tmp_path: Path) -> None:
    """oslc_cm:closed is true only for done; landed reads false, as the agreement says."""
    g = _queue(tmp_path, {"W1": "landed", "W2": "done"})
    assert str(g.value(waypoint_uri("a", "W1"), OSLC_CM.closed)) == "false"
    assert str(g.value(waypoint_uri("a", "W2"), OSLC_CM.closed)) == "true"
