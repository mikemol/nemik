# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1147: a window's adds split by what caused them, so atomization is told from new work."""

from datetime import UTC, datetime

from nemik.history import (
    ROW_LINES,
    Causes,
    QueueDoc,
    cause_counts,
    cause_row,
    stamp_causes,
)

SINCE = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
NEW = "2026-10-26T14:00:00Z"
OLD = "2026-10-20T00:00:00Z"
BASE: QueueDoc = {
    "waypoints": [
        {"symbol": "W1", "status": "ready"},
        {"symbol": "W2", "status": "ready"},
    ],
    "residue": [],
}
NOW: QueueDoc = {
    "waypoints": [
        {"symbol": "W1", "status": "ready"},
        {"symbol": "W2", "status": "done"},
        {"symbol": "W3", "status": "ready", "caused_by": "W1"},
        {"symbol": "W4", "status": "ready", "caused_by": "W2"},
        {"symbol": "W5", "status": "ready", "caused_by": "github-8f"},
        {"symbol": "W6", "status": "ready", "caused_by": "mtools:W9"},
        {"symbol": "W7", "status": "ready"},
    ],
    "residue": [],
}
STAMPED: QueueDoc = {
    "waypoints": [
        {"symbol": "W1", "status": "ready", "issued_at": OLD},
        {"symbol": "W2", "status": "ready", "issued_at": NEW, "caused_by": "W1"},
        {"symbol": "W3", "status": "ready", "issued_at": NEW},
        {"symbol": "W4", "status": "ready", "issued_at": OLD, "caused_by": "W1"},
    ],
    "residue": [],
}
HEAD = "fleet since -1d: added 10: child 3, promoted 1, outside 5, none 1"


def test_a_child_of_an_open_card_is_told_from_a_promotion_of_a_done_one() -> None:
    """W3 hangs off the open W1, W4 off the done W2; the rest are outside or have no cause."""
    assert cause_counts(BASE, NOW) == (1, 1, 2, 1)


def test_an_unchanged_queue_added_nothing() -> None:
    """Nothing new, nothing split."""
    assert cause_counts(NOW, NOW) == (0, 0, 0, 0)


def test_a_queue_outside_git_is_split_from_its_stamps() -> None:
    """Only the cards issued in the window count, each by the card it is caused by."""
    assert stamp_causes(STAMPED, SINCE) == (1, 0, 0, 1)


def test_the_cause_row_totals_and_lists_only_the_repos_that_added() -> None:
    """A quiet repo has no line; the busiest comes first."""
    rows: dict[str, Causes] = {"a": (2, 1, 0, 0), "b": (0, 0, 0, 0), "c": (1, 0, 5, 1)}
    lines = cause_row(rows, "-1d")
    assert lines[0] == HEAD
    assert [line.split(":")[0] for line in lines[1:]] == ["c", "a"]


def test_the_cause_row_never_exceeds_its_line_cap() -> None:
    """Many adding repos fold into a tail line."""
    rows: dict[str, Causes] = {f"r{n:02d}": (1, 0, 0, 0) for n in range(25)}
    lines = cause_row(rows, "-1d")
    assert len(lines) == ROW_LINES
    assert lines[-1] == "+17 more repos added"
