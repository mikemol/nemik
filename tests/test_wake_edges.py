# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W851: waking a finished witnessed card sends every cross-repo edge its letter, once."""

import json
from pathlib import Path

from nemik.witnesses import RECORD, wake

ALPHA: dict[str, list[dict[str, object]]] = {
    "waypoints": [
        {"symbol": "W1", "status": "done"},
        {"symbol": "W2", "status": "blocked", "blocked_on": ["W1"]},
    ]
}
BETA: dict[str, list[dict[str, object]]] = {
    "waypoints": [
        {"symbol": "W5", "status": "blocked", "blocked_on": ["alpha:W1"]},
        {"symbol": "W6", "status": "ready", "caused_by": "alpha:W1"},
    ]
}
NOW = "2026-10-22T10:00:00Z"
LATER = "2026-10-23T10:00:00Z"


def _fleet(root: Path) -> None:
    """Write both queues under `root` with an inbox each."""
    for repo, queue in (("alpha", ALPHA), ("beta", BETA)):
        state = root / repo / ".claude" / "paths-forward.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps(queue), encoding="utf-8")
        (root / repo / "inbox").mkdir()


def _written(root: Path, letters: list[Path]) -> list[str]:
    """Sort the letters as paths under `root`.

    Args:
        root: The fleet root.
        letters: The letters a wake wrote.

    Returns:
        Each letter's path relative to `root`, sorted.

    """
    return sorted(p.relative_to(root).as_posix() for p in letters)


def test_a_wake_writes_the_local_letter_and_one_letter_per_cross_repo_edge(
    tmp_path: Path,
) -> None:
    """Alpha's waiter gets the witness letter; beta gets one letter for each of its two edges."""
    _fleet(tmp_path)
    letters = wake(tmp_path, "alpha", "W1", "q", NOW)
    assert _written(tmp_path, letters) == [
        "alpha/inbox/2026-10-22-nemik-witness-alpha-W1.md",
        "beta/inbox/2026-10-22-nemik-edge-alpha-W1-blocked_on-W5.md",
        "beta/inbox/2026-10-22-nemik-edge-alpha-W1-caused_by-W6.md",
    ]


def test_a_later_wake_sends_no_second_cross_repo_letter(tmp_path: Path) -> None:
    """The record holds both edges, so the next day's wake writes only the local letter."""
    _fleet(tmp_path)
    wake(tmp_path, "alpha", "W1", "q", NOW)
    again = wake(tmp_path, "alpha", "W1", "q", LATER)
    assert _written(tmp_path, again) == [
        "alpha/inbox/2026-10-23-nemik-witness-alpha-W1.md"
    ]
    assert (tmp_path / RECORD).read_text(encoding="utf-8").splitlines() == [
        "alpha:W1 blocked_on beta:W5 2026-10-22",
        "alpha:W1 caused_by beta:W6 2026-10-22",
    ]
