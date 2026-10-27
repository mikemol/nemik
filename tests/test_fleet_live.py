# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1112: a card minted after the last commit shows in a window at once."""

from pathlib import Path

from nemik.history import QueueDoc, burn_counts, live_queue

COMMITTED: QueueDoc = {
    "waypoints": [{"symbol": "W1", "status": "ready"}],
    "residue": [],
}
ON_DISK = (
    '{"waypoints": [{"symbol": "W1", "status": "ready"},'
    ' {"symbol": "W2", "status": "ready", "caused_by": "W1"}], "residue": []}\n'
)


def _write(repo: Path, text: str) -> None:
    """Put a queue file where the repo keeps it."""
    (repo / ".claude").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "paths-forward.json").write_text(text, encoding="utf-8")


def test_a_card_on_disk_but_not_committed_counts_as_added(tmp_path: Path) -> None:
    """HEAD has W1; the file also has W2, so a window from HEAD sees one add, not none."""
    _write(tmp_path, ON_DISK)
    now = live_queue(tmp_path, COMMITTED)
    assert burn_counts(COMMITTED, now) == (0, 0, 1, 1)
    assert burn_counts(COMMITTED, COMMITTED) == (0, 0, 0, 1)


def test_a_missing_file_reads_as_the_committed_queue(tmp_path: Path) -> None:
    """No queue file on disk: the committed copy stands."""
    assert live_queue(tmp_path, COMMITTED) == COMMITTED


def test_a_file_half_written_reads_as_the_committed_queue(tmp_path: Path) -> None:
    """A truncated file is not an error of the row; the committed copy stands."""
    _write(tmp_path, '{"waypoints": [{"symbol": "W1"')
    assert live_queue(tmp_path, COMMITTED) == COMMITTED
