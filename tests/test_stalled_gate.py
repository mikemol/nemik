# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W682: the waypoints a gating commit stack carries, read from the tool's public mode.

nemik:W2125: named_waypoints reads the tool's answer as a tracker.Tree (the pinned Codon refuses
json.loads into an object), so each answer here is JSON text parsed by parse_tree.
"""

import json

from nemik.tracker import parse_tree
from nemik.work import named_waypoints

LIVE = [
    {"key": "1", "state": "inflight", "waypoints": ["W762"], "began_ns": 7},
    {"key": "2", "state": "queued", "waypoints": ["W766", "W694"], "began_ns": 8},
]


def _named(answer: object) -> set[str]:
    """Name the waypoints of an answer given as the Python value json.dumps would write.

    Returns:
        The waypoints the in-gate reader names.

    """
    return named_waypoints(parse_tree(json.dumps(answer)))


def test_every_waypoint_of_every_live_stack_is_named() -> None:
    """Two entries, three waypoints between them."""
    assert _named(LIVE) == {"W762", "W766", "W694"}


def test_an_answer_that_is_not_a_list_of_entries_names_nothing() -> None:
    """An error object, an entry without waypoints and a bare string are all ignored."""
    assert _named({"error": "x"}) == set()
    assert _named([{"key": "1"}, "W1", None]) == set()
    assert _named([]) == set()


def test_a_null_or_absent_waypoints_member_names_nothing() -> None:
    """A null member and an absent one read alike, as they did when the reader used .get."""
    assert _named([{"waypoints": None}, {"key": "2"}]) == set()
    assert _named([{"waypoints": ["W1", 2, None]}]) == {"W1"}
