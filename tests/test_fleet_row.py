# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1112: the fleet's burndown in a few lines, the host's queue counted from its stamps."""

from datetime import UTC, datetime

from nemik.history import (
    ROW_LINES,
    Counts,
    QueueDoc,
    burn_counts,
    fleet_row,
    stamp_counts,
    window_start,
)

SINCE = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
OLD = "2026-10-20T00:00:00Z"
DOC: QueueDoc = {
    "waypoints": [
        {
            "symbol": "W1",
            "status": "done",
            "issued_at": OLD,
            "completed": "2026-10-26T13:00:00Z",
        },
        {
            "symbol": "W2",
            "status": "done",
            "issued_at": OLD,
            "completed": "2026-10-25T13:00:00Z",
        },
        {"symbol": "W3", "status": "ready", "issued_at": OLD},
        {"symbol": "W4", "status": "ready", "issued_at": "2026-10-26T14:00:00Z"},
    ],
    "residue": [
        {"symbol": "W5", "dropped_at": "2026-10-26T15:00:00Z"},
        {"symbol": "W6", "dropped_at": "2026-10-01T15:00:00Z"},
    ],
}
BASE: QueueDoc = {
    "waypoints": [
        {"symbol": "W1", "status": "ready"},
        {"symbol": "W2", "status": "ready"},
        {"symbol": "W3", "status": "ready"},
    ],
    "residue": [],
}
NOW: QueueDoc = {
    "waypoints": [
        {"symbol": "W1", "status": "done"},
        {"symbol": "W3", "status": "ready"},
        {"symbol": "W7", "status": "ready"},
    ],
    "residue": [{"symbol": "W2"}],
}
QUIET: Counts = (0, 0, 0, 5)


def test_the_stamps_alone_say_what_closed_dropped_and_was_added() -> None:
    """A card finished before the window is not counted; one issued after it is added."""
    assert stamp_counts(DOC, SINCE) == (1, 1, 1, 1)


def test_two_committed_copies_count_as_the_baseline_report_does() -> None:
    """The plan is the cards open at the baseline: W1 closed, W2 dropped, W3 open, W7 added."""
    assert burn_counts(BASE, NOW) == (1, 1, 1, 1)


def test_a_window_names_its_instant_and_a_revision_names_none() -> None:
    """Only a window or a zoned instant is a time; a revision is for git."""
    assert window_start("2026-10-26T12:00Z") == SINCE
    assert window_start("-45m") is not None
    assert window_start("abc1234") is None


def test_the_fleet_row_totals_the_net_and_lists_only_the_repos_that_changed() -> None:
    """Closed plus dropped less added is the net; a quiet repo has no line."""
    rows = {"a": (2, 1, 0, 5), "b": QUIET, "c": (0, 0, 4, 5)}
    lines = fleet_row(rows, "-1d")
    assert lines[0].startswith("fleet since -1d: closed 2, dropped 1, added 4, net -1")
    assert [line.split(":")[0] for line in lines[1:]] == ["c", "a"]


def test_the_fleet_row_never_exceeds_its_line_cap() -> None:
    """Many changed repos fold into a tail line, so a hook's cap holds."""
    rows: dict[str, Counts] = {f"r{n:02d}": (1, 0, 0, 5) for n in range(25)}
    lines = fleet_row(rows, "-45m")
    assert len(lines) == ROW_LINES
    assert lines[-1] == "+17 more repos changed"
