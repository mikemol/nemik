# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1139: a queue with no git history gets its weekly rows from its own stamps."""

import json
from pathlib import Path

from nemik.history import (
    QueueDoc,
    Snapshot,
    Waypoint,
    snapshots,
    stamp_snapshots,
    weekly,
)

OPENED_IN_FIRST_WEEK = 2
CLOSED_IN_FIRST_WEEK = 1
TWO_WEEKS = 2
QUEUE = Path(".claude") / "paths-forward.json"
# one card closed, one open, one issued a week later, one with no stamp at all
CARDS: list[Waypoint] = [
    {
        "symbol": "W1",
        "status": "done",
        "issued_at": "2026-11-02T10:00:00Z",
        "completed": "20261103T120000Z",
    },
    {"symbol": "W2", "status": "ready", "issued_at": "2026-11-02T11:00:00Z"},
    {"symbol": "W3", "status": "blocked", "issued_at": "2026-11-10T09:00:00Z"},
    {"symbol": "W4", "status": "ready"},
]
DOC: QueueDoc = {"waypoints": CARDS}


def _queue(tmp_path: Path) -> Path:
    """Write the cards as a queue file outside any repository.

    Returns:
        The queue file's path.

    """
    path = tmp_path / QUEUE
    path.parent.mkdir()
    path.write_text(json.dumps(DOC), encoding="utf-8")
    return path


def _states(snap: Snapshot) -> dict[str, str]:
    """Give each card of a snapshot with its status.

    Returns:
        The status by symbol.

    """
    return {str(w["symbol"]): str(w["status"]) for w in snap[1]["waypoints"]}


def test_a_queue_with_no_git_history_reads_its_stamps(tmp_path: Path) -> None:
    """The snapshots are one per distinct stamp, oldest first, and a card with no stamp is out."""
    _queue(tmp_path)
    snaps = snapshots(tmp_path)
    assert [at.isoformat() for at, _ in snaps] == [
        "2026-11-02T10:00:00+00:00",
        "2026-11-02T11:00:00+00:00",
        "2026-11-03T12:00:00+00:00",
        "2026-11-10T09:00:00+00:00",
    ]
    assert set(_states(snaps[-1])) == {"W1", "W2", "W3"}


def test_a_closed_card_was_open_before_its_close() -> None:
    """W1 reads ready until its `completed` stamp and done from then on."""
    first, _, closed, _ = stamp_snapshots(DOC)
    assert _states(first) == {"W1": "ready"}
    assert _states(closed)["W1"] == "done"


def test_the_weekly_rows_count_what_opened_and_closed(tmp_path: Path) -> None:
    """Two ISO weeks: two cards opened and one closed in the first, one opened in the second."""
    _queue(tmp_path)
    rows = weekly(snapshots(tmp_path))
    assert len(rows) == TWO_WEEKS
    first, second = rows
    opened: object = first["opened"]
    closed: object = first["closed"]
    later: object = second["opened"]
    assert (opened, closed, later) == (OPENED_IN_FIRST_WEEK, CLOSED_IN_FIRST_WEEK, 1)


def test_no_queue_file_is_no_snapshots(tmp_path: Path) -> None:
    """With neither git history nor a queue file there is nothing to read."""
    assert snapshots(tmp_path) == []


def test_since_never_falls_back_to_the_stamps(tmp_path: Path) -> None:
    """`since` asks about commits, so a queue outside git answers it with nothing."""
    _queue(tmp_path)
    assert snapshots(tmp_path, since="2026-01-01") == []
