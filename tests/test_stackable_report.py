# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W613: the stackable report reads manifests from the graph and picks in rank order."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.stackable import manifest, report


def _queue(tmp_path: Path) -> Graph:
    """Read a queue of three ready cards.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The queue's graph: W1 plans a.py and b.py, W2 plans b.py, W3 plans nothing.

    """
    residue: list[str] = []
    cards: list[dict[str, object]] = [
        {"symbol": "W1", "title": "t", "status": "ready", "manifest": ["a.py", "b.py"]},
        {"symbol": "W2", "title": "t", "status": "ready", "manifest": ["b.py"]},
        {"symbol": "W3", "title": "t", "status": "ready"},
    ]
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


def test_the_manifest_is_read_from_the_graph(tmp_path: Path) -> None:
    """A card's planned files come back sorted; a card with none gives an empty list."""
    g = _queue(tmp_path)
    assert manifest(g, "a", "W1") == ["a.py", "b.py"]
    assert manifest(g, "a", "W3") == []


def test_the_report_stacks_the_first_and_makes_the_overlapping_one_wait(
    tmp_path: Path,
) -> None:
    """W1 takes b.py first, so W2 waits; W3 has no manifest and is counted, not stacked."""
    g = _queue(tmp_path)
    ranked: list[dict[str, object]] = [
        {"symbol": "W1"},
        {"symbol": "W2"},
        {"symbol": "W3"},
    ]
    lines = report(g, "a", ranked, [])
    assert lines[0].startswith("STACK")
    assert "a:W1" in lines[0]
    assert lines[1].startswith("WAITING")
    assert "a:W2" in lines[1]
    assert lines[-1] == "1 stackable of 3 ready; 1 have no manifest"


def test_a_staged_file_keeps_its_card_out(tmp_path: Path) -> None:
    """With b.py already staged neither planned card can join."""
    g = _queue(tmp_path)
    ranked: list[dict[str, object]] = [{"symbol": "W1"}, {"symbol": "W2"}]
    assert report(g, "a", ranked, ["b.py"])[-1].startswith("0 stackable")
