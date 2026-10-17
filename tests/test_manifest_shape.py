# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W612: a ready leaf with no manifest is named; planned, non-leaf and large cards differ."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import NEMIK, queue_graph, waypoint_uri
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


def _card(symbol: str, **more: object) -> dict[str, object]:
    """Build a ready card.

    Args:
        symbol: The card's symbol.
        **more: Further fields.

    Returns:
        The card.

    """
    return {"symbol": symbol, "title": symbol, "status": "ready", **more}


def _named(g: Graph, word: str) -> set[str]:
    """Collect the symbols whose finding contains a phrase.

    Args:
        g: The queue's graph.
        word: A phrase of the finding's message.

    Returns:
        The symbols named.

    """
    rows = findings(f"manifest-{id(g)}-{word}", g, shapes())
    named = {str(focus) for focus, _, m in rows if word in m}
    return {s for s in ("W1", "W2", "W3", "W4") if str(waypoint_uri("a", s)) in named}


def test_the_adapter_reads_the_manifest_and_the_size(tmp_path: Path) -> None:
    """The planned files and the size class become triples on the card."""
    g = _queue(tmp_path, [_card("W1", manifest=["a.py", "b.py"], size_class="small")])
    node = waypoint_uri("a", "W1")
    assert {str(o) for o in g.objects(node, NEMIK.plannedPath)} == {"a.py", "b.py"}
    assert [str(o) for o in g.objects(node, NEMIK.sizeClass)] == ["small"]


def test_only_a_ready_leaf_without_a_manifest_is_named(tmp_path: Path) -> None:
    """W1 is planned; W3 has an open enabler (W2), so it is no leaf; W2 and W4 are bare leaves."""
    g = _queue(
        tmp_path,
        [
            _card("W1", manifest=["a.py"]),
            _card("W2", enables=["W3"]),
            _card("W3", manifest=["c.py"]),
            _card("W4"),
        ],
    )
    assert _named(g, "no manifest") == {"W2", "W4"}


def test_a_large_card_is_told_to_atomize(tmp_path: Path) -> None:
    """Only the card declared large draws the oversize finding."""
    g = _queue(
        tmp_path,
        [_card("W1", size_class="large"), _card("W2", size_class="small")],
    )
    assert _named(g, "declared size large") == {"W1"}
