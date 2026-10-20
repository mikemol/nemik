# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W682: the waypoints a gating commit stack carries, read from the tool's public mode."""

from nemik.stalled import named_waypoints

LIVE = [
    {"key": "1", "state": "inflight", "waypoints": ["W762"], "began_ns": 7},
    {"key": "2", "state": "queued", "waypoints": ["W766", "W694"], "began_ns": 8},
]


def test_every_waypoint_of_every_live_stack_is_named() -> None:
    """Two entries, three waypoints between them."""
    assert named_waypoints(LIVE) == {"W762", "W766", "W694"}


def test_an_answer_that_is_not_a_list_of_entries_names_nothing() -> None:
    """An error object, an entry without waypoints and a bare string are all ignored."""
    assert named_waypoints({"error": "x"}) == set()
    assert named_waypoints([{"key": "1"}, "W1", None]) == set()
    assert named_waypoints([]) == set()
