# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W842: a card waiting on a landed card keeps waiting; done or dropped lifts it."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import NEMIK, queue_graph, waypoint_uri
from nemik.blocks import annotate


def _annotated(tmp_path: Path, blocker_status: str) -> Graph:
    """Read a queue where W1 is blocked on W2, and annotate it.

    Args:
        tmp_path: A scratch directory.
        blocker_status: The status W2 is in.

    Returns:
        The annotated graph.

    """
    waiter: dict[str, object] = {
        "symbol": "W1",
        "title": "waiter",
        "status": "blocked",
        "blocked_on": ["W2"],
    }
    blocker: dict[str, object] = {
        "symbol": "W2",
        "title": "blocker",
        "status": blocker_status,
    }
    cards = [waiter, blocker]
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
    g = queue_graph("a", path)
    annotate(g)
    return g


def _lifted(g: Graph) -> bool:
    """Say whether the waiter is marked as having all its blockers landed.

    Returns:
        True when W1 carries allBlockersLanded.

    """
    return g.value(waypoint_uri("a", "W1"), NEMIK.allBlockersLanded) is not None


def test_a_waiter_on_a_done_card_is_marked_lifted(tmp_path: Path) -> None:
    """Done is the control: the blocker has landed for good, so the waiter should be ready."""
    assert _lifted(_annotated(tmp_path, "done"))


def test_a_waiter_on_a_landed_card_keeps_waiting(tmp_path: Path) -> None:
    """A landed change may not be deployed, so the block stays until the card is done."""
    assert not _lifted(_annotated(tmp_path, "landed"))
