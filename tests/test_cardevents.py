# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W744: the difference between two snapshots of a queue is a list of events."""

from nemik.cardevents import Queue, events_of

SHA = "abc123"
AT = "2026-10-19T12:00:00+00:00"


def test_a_new_card_is_minted_and_a_status_change_is_one_event() -> None:
    """W2 is new; W1 went from ready to done; nothing else is reported."""
    old: Queue = {"waypoints": [{"symbol": "W1", "status": "ready"}], "residue": []}
    new: Queue = {
        "waypoints": [
            {"symbol": "W1", "status": "done"},
            {"symbol": "W2", "status": "ready"},
        ],
        "residue": [],
    }
    assert events_of("nemik", old, new, SHA, AT) == [
        ("nemik:W1", AT, "status", "ready", "done", SHA),
        ("nemik:W2", AT, "card", "", "minted", SHA),
    ]


def test_lists_are_joined_and_a_dropped_card_is_told_from_a_removed_one() -> None:
    """blocked_on changes as a joined string; residue says dropped, absence says removed."""
    old: Queue = {
        "waypoints": [
            {"symbol": "W1", "status": "blocked", "blocked_on": ["mtools:W9"]},
            {"symbol": "W2", "status": "ready"},
            {"symbol": "W3", "status": "ready"},
        ],
        "residue": [],
    }
    new: Queue = {
        "waypoints": [
            {"symbol": "W1", "status": "blocked", "blocked_on": ["W5", "W6"]}
        ],
        "residue": [{"symbol": "W2"}],
    }
    assert events_of("nemik", old, new, SHA, AT) == [
        ("nemik:W1", AT, "blocked_on", "mtools:W9", "W5,W6", SHA),
        ("nemik:W2", AT, "card", "ready", "dropped", SHA),
        ("nemik:W3", AT, "card", "ready", "removed", SHA),
    ]


def test_two_equal_snapshots_make_no_events() -> None:
    """A snapshot that changes nothing is silent."""
    same: Queue = {"waypoints": [{"symbol": "W1", "status": "ready"}], "residue": []}
    assert not events_of("nemik", same, same, SHA, AT)
