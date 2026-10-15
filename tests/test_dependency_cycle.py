# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W484: a ring is named in order by the shared walker, and W331's warning carries the name."""

import json
import tempfile
from pathlib import Path

from rdflib import Graph
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, waypoint_uri
from nemik.blocks import dependency_cycles
from nemik.check import survey


def _ring(last_state: Node) -> Graph:
    # r:W1 enables r:W2 enables r:W3, and r:W3 enables r:W1: mtools:W1134's ring of three
    g = Graph()
    for sym, state in (("W1", NEMIK.Ready), ("W2", NEMIK.Ready), ("W3", last_state)):
        g.add((waypoint_uri("r", sym), OSLC_CM.state, state))
    for a, b in (("W1", "W2"), ("W2", "W3"), ("W3", "W1")):
        g.add((waypoint_uri("r", a), NEMIK.enables, waypoint_uri("r", b)))
    return g


def test_a_ring_of_three_is_found_once_in_order() -> None:
    ring = [waypoint_uri("r", s) for s in ("W1", "W2", "W3")]
    assert dependency_cycles(_ring(NEMIK.Ready)) == [tuple(ring)]


def test_a_done_member_breaks_the_ring() -> None:
    assert dependency_cycles(_ring(NEMIK.Done)) == []


def test_the_deadlock_warning_names_the_ring_in_order() -> None:
    # three blocked cards waiting on one another round a ring, all on agents (W331 warns)
    cards = [
        {
            "symbol": s,
            "title": s,
            "status": "blocked",
            "blocked_on": [b],
            "blocked_kind": "agent",
            "next_bounded_step": "x",
        }
        for s, b in (("W1", "W3"), ("W2", "W1"), ("W3", "W2"))
    ]
    state = {
        "version": 1,
        "project_root": "/x",
        "counter": 3,
        "residue": [],
        "waypoints": cards,
    }
    with tempfile.TemporaryDirectory() as tmp:
        queue = Path(tmp) / "a" / ".claude" / "paths-forward.json"
        queue.parent.mkdir(parents=True)
        queue.write_text(json.dumps(state))
        found = {
            sym: msg
            for _, _, findings in survey(Path(tmp))
            for sev, sym, msg in findings
            if sev == "Warning" and "dependency cycle" in msg
        }
    assert sorted(found) == ["W1", "W2", "W3"]
    assert "a:W1 -> a:W2 -> a:W3 -> a:W1" in found["W1"]
    assert "a:W2 -> a:W3 -> a:W1 -> a:W2" in found["W2"]
