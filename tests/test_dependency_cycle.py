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
    """The walker names the ring W1, W2, W3 once, in enable order."""
    ring = [waypoint_uri("r", s) for s in ("W1", "W2", "W3")]
    assert dependency_cycles(_ring(NEMIK.Ready)) == [tuple(ring)]


def test_a_done_member_breaks_the_ring() -> None:
    """A finished card waits on nothing, so the ring is no longer one."""
    assert dependency_cycles(_ring(NEMIK.Done)) == []


def test_the_deadlock_warning_names_the_ring_in_order() -> None:
    """Each member's warning spells the ring starting at that member."""
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


def _card(symbol: str, blocked_on: list[str], enables: list[str]) -> dict[str, object]:
    """Build one blocked card on an agent.

    Args:
        symbol: The card's symbol.
        blocked_on: What it waits on.
        enables: What it enables.

    Returns:
        The queue row.

    """
    return {
        "symbol": symbol,
        "title": symbol,
        "status": "blocked",
        "blocked_on": blocked_on,
        "blocked_kind": "agent",
        "enables": enables,
        "next_bounded_step": "x",
    }


def _queue(root: Path, repo: str, cards: list[dict[str, object]]) -> None:
    """Write one repo's queue under root."""
    state = {
        "version": 1,
        "project_root": f"/{repo}",
        "counter": 9,
        "residue": [],
        "waypoints": cards,
    }
    queue = root / repo / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    queue.write_text(json.dumps(state))


def test_a_ring_through_a_bare_repo_wait_is_a_warning_naming_every_card() -> None:
    """nemik:W576: linux-sources:W323 waits on gcalculus:W265, which waits on 'linux-sources'.

    The bare name draws no card edge; the repo's card that enables the waiter (W330) is the claim,
    and it waits on W323, so the ring W265 -> W323 -> W330 -> W265 crosses two repos.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _queue(
            root,
            "linux-sources",
            [
                _card("W323", ["gcalculus:W265"], []),
                _card("W330", ["W323"], ["gcalculus:W265"]),
            ],
        )
        _queue(root, "gcalculus", [_card("W265", ["linux-sources"], [])])
        found = {
            (repo, sym): msg
            for repo, _, findings in survey(root)
            for sev, sym, msg in findings
            if sev == "Warning" and "dependency cycle" in msg
        }
    assert sorted(found) == [
        ("gcalculus", "W265"),
        ("linux-sources", "W323"),
        ("linux-sources", "W330"),
    ]
    assert all("gcalculus:W265" in msg for msg in found.values())
    assert all("linux-sources:W330" in msg for msg in found.values())
