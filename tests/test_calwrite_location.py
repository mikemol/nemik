# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W722: a waypoint's location is its calendar event's LOCATION."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.calwrite import events, uid


def _graph(tmp_path: Path) -> Graph:
    """Read a queue of two dated cards, one with a location.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The queue's graph.

    """
    placed: dict[str, str] = {
        "symbol": "W3",
        "title": "drive",
        "status": "ready",
        "due": "20261001",
        "location": "Ann Arbor, MI; room 4",
    }
    bare: dict[str, str] = {
        "symbol": "W4",
        "title": "call",
        "status": "ready",
        "due": "20261002",
    }
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/x",
        "counter": 4,
        "residue": [],
        "waypoints": [placed, bare],
    }
    path = tmp_path / "life.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("life", path)


def test_a_location_is_escaped_as_text_and_a_card_without_one_writes_none(
    tmp_path: Path,
) -> None:
    """The comma and the semicolon are escaped; the other card has no LOCATION line."""
    lines = {e[1]: e for e in events(_graph(tmp_path), ["life"])}
    assert "LOCATION:Ann Arbor\\, MI\\; room 4" in lines[f"UID:{uid('life:W3')}"]
    assert not any(x.startswith("LOCATION") for x in lines[f"UID:{uid('life:W4')}"])
