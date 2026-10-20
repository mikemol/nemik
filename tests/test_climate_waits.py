# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W753: the waits are the lengths of finished stints in a status."""

from nemik.climate import waits_of

SHA = "abc123"
DAY = "2026-10-%02dT00:00:00+00:00"


def _at(day: int) -> str:
    return DAY % day


def test_each_finished_stint_is_a_wait_for_its_status() -> None:
    """Ready day 1-3, blocked day 3-4, ready day 4-9, done from day 9 (never finishes)."""
    events = [
        ("a:W1", _at(1), "status", "", "ready", SHA),
        ("a:W1", _at(3), "status", "ready", "blocked", SHA),
        ("a:W1", _at(4), "status", "blocked", "ready", SHA),
        ("a:W1", _at(9), "status", "ready", "done", SHA),
    ]
    got = waits_of(events)
    assert got["ready"] == [2.0, 5.0]
    assert got["blocked"] == [1.0]
    assert "done" not in got


def test_a_dropped_card_ends_its_stint() -> None:
    """The stint ends when the card leaves; the card has no status after."""
    events = [
        ("a:W1", _at(1), "status", "", "ready", SHA),
        ("a:W1", _at(4), "card", "ready", "dropped", SHA),
    ]
    assert waits_of(events) == {"ready": [3.0]}
