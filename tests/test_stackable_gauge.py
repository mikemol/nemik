# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W613: nemik_stackable counts the ready cards one commit stack can carry now."""

import json
from pathlib import Path

from rdflib import Graph

from nemik import metrics
from nemik.adapter import queue_graph
from nemik.stackable import stackable_count


def _fleet(root: Path) -> Graph:
    """Lay out one repo whose queue has three ready cards.

    Args:
        root: The fleet root.

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
        "project_root": str(root / "alpha"),
        "counter": len(cards),
        "residue": residue,
        "waypoints": cards,
    }
    path = root / "alpha" / ".claude" / "paths-forward.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("alpha", path)


def test_the_count_skips_the_overlapping_and_the_unplanned(tmp_path: Path) -> None:
    """W1 takes b.py, so W2 waits, and W3 has no manifest: one card stacks."""
    ranked: list[dict[str, object]] = [
        {"symbol": "W1"},
        {"symbol": "W2"},
        {"symbol": "W3"},
    ]
    assert stackable_count(_fleet(tmp_path), "alpha", ranked, []) == 1


def test_a_staged_file_keeps_a_card_out(tmp_path: Path) -> None:
    """With a.py already staged, W1 cannot stack, and W2 (b.py only) can."""
    ranked: list[dict[str, object]] = [{"symbol": "W1"}, {"symbol": "W2"}]
    assert stackable_count(_fleet(tmp_path), "alpha", ranked, ["a.py"]) == 1


def test_a_repo_with_a_queue_gets_a_sample(tmp_path: Path) -> None:
    """The gauge answers its TYPE line and one sample for the repo, counting W1 only."""
    g = _fleet(tmp_path)
    lines = metrics.stackable_lines(tmp_path, g)
    assert lines == ["# TYPE nemik_stackable gauge", 'nemik_stackable{repo="alpha"} 1']
