# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W609: nemik_cards_completed_24h counts the cards the queue's history shows closing."""

from pathlib import Path

import pytest

from nemik import history
from nemik.metrics import completed_in


def _queue(*done: str) -> dict[str, object]:
    """Build a queue of W1 and W2 with the named cards done.

    Args:
        *done: The symbols that are done.

    Returns:
        A parsed queue.

    """
    cards = [
        {"symbol": s, "status": "done" if s in done else "ready"} for s in ("W1", "W2")
    ]
    return {"waypoints": cards, "residue": []}


def _start(repo: Path, spec: str | None) -> str | None:
    """Resolve every window start to the same revision.

    Args:
        repo: The repo's directory, unused.
        spec: The window start, unused.

    Returns:
        The revision name the fake history answers to.

    """
    del repo, spec
    return "start"


def _history(repo: Path, rev: str | None) -> dict[str, object]:
    """Answer the committed queue at HEAD and at the window's start.

    Args:
        repo: The repo's directory, unused.
        rev: The revision asked for.

    Returns:
        W1 and W2 done at HEAD; only W2 at the start.

    """
    del repo
    both = {"HEAD": _queue("W1", "W2"), "start": _queue("W2")}
    return both.get(str(rev), {})


def _none(repo: Path, rev: str | None) -> dict[str, object]:
    """Answer as a directory with no git history does.

    Args:
        repo: The repo's directory, unused.
        rev: The revision asked for, unused.

    Returns:
        An empty queue.

    """
    del repo, rev
    return {}


def test_a_card_closed_since_the_start_of_the_window_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """W2 was done at the window's start and W1 is done now: one card closed in the window."""
    monkeypatch.setattr(history, "resolve", _start)
    monkeypatch.setattr(history, "queue_at", _history)
    assert completed_in(tmp_path, "2026-10-03T00:00:00") == 1


def test_a_directory_with_no_history_reads_as_unknown_not_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An export layout has no git; a sample of 0 there would claim a quiet day."""
    monkeypatch.setattr(history, "queue_at", _none)
    assert completed_in(tmp_path, "2026-10-03T00:00:00") is None
