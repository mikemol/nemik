# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1112: a card is added in a window when it was issued in it, and both readers agree."""

from datetime import UTC, datetime

from nemik.history import QueueDoc, burn_counts, cause_counts

SINCE = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
OLD = "2026-10-05T17:26:51Z"
NEW = "2026-10-26T14:00:00Z"
BASE: QueueDoc = {
    "waypoints": [{"symbol": "W1", "status": "ready"}],
    "residue": [],
}
NOW: QueueDoc = {
    "waypoints": [
        {"symbol": "W1", "status": "ready"},
        {"symbol": "W2", "status": "ready", "issued_at": OLD},
        {"symbol": "W3", "status": "ready", "issued_at": NEW, "caused_by": "W1"},
        {"symbol": "W4", "status": "ready"},
    ],
    "residue": [{"symbol": "W5"}],
}


def test_a_new_symbol_issued_before_the_window_is_not_an_add() -> None:
    """The rosettapkg case: cards new to the last commit but issued long before the window."""
    assert burn_counts(BASE, NOW, SINCE) == (0, 0, 3, 1)
    assert burn_counts(BASE, NOW) == (0, 0, 4, 1)


def test_by_cause_counts_the_same_adds_as_the_compact_row() -> None:
    """The two readers agree on the total, and a card added then dropped counts under none."""
    split = cause_counts(BASE, NOW, SINCE)
    assert sum(split) == burn_counts(BASE, NOW, SINCE)[2]
    assert split == (1, 0, 0, 2)


def test_without_a_window_every_new_symbol_counts() -> None:
    """A revision names no instant to compare issued_at with, so nothing is set aside."""
    assert sum(cause_counts(BASE, NOW)) == burn_counts(BASE, NOW)[2]
