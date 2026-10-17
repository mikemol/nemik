# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W355: a card that goes from done back to open is a change failure."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from nemik import history
from nemik.metrics import reopened_lines

TWICE = 2


def _queue(*pairs: tuple[str, str]) -> dict[str, object]:
    """Build a queue of cards with the given symbols and statuses.

    Args:
        *pairs: (symbol, status) for each card.

    Returns:
        A parsed queue.

    """
    cards = [{"symbol": s, "status": st} for s, st in pairs]
    return {"waypoints": cards, "residue": []}


def _at(repo: Path, rev: str | None) -> dict[str, object]:
    """Answer the committed queue at HEAD and at the window's start.

    Args:
        repo: The repo's directory, unused.
        rev: The revision asked for.

    Returns:
        W1 done at the start, ready again at HEAD.

    """
    del repo
    both = {
        "HEAD": _queue(("W1", "ready")),
        "start": _queue(("W1", "done")),
    }
    return both.get(str(rev), {})


def _start(repo: Path, spec: str | None) -> str | None:
    """Resolve every window start to the same revision.

    Args:
        repo: The repo's directory, unused.
        spec: The window start, unused.

    Returns:
        The revision the fake history answers to.

    """
    del repo, spec
    return "start"


def _commits(
    repo: Path, since: str | None = None
) -> list[tuple[datetime, dict[str, object]]]:
    """List the queue commits in the window: W1 reopened, then done, then reopened again.

    Args:
        repo: The repo's directory, unused.
        since: The window start, unused.

    Returns:
        Three snapshots.

    """
    del repo, since
    at = datetime(2026, 10, 17, tzinfo=UTC)
    return [
        (at, _queue(("W1", "ready"))),
        (at, _queue(("W1", "done"))),
        (at, _queue(("W1", "ready"))),
    ]


def test_each_done_to_open_transition_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Done at the start, reopened, done again, reopened again: two failures."""
    monkeypatch.setattr(history, "queue_at", _at)
    monkeypatch.setattr(history, "resolve", _start)
    monkeypatch.setattr(history, "snapshots", _commits)
    count = history.reopened_since(tmp_path, "2026-10-16T00:00:00")
    assert count == TWICE


def test_the_gauge_prints_a_sample_per_repo_with_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The family has a TYPE line and one sample for the repo."""
    queue = tmp_path / "alpha" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    queue.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(history, "queue_at", _at)
    monkeypatch.setattr(history, "resolve", _start)
    monkeypatch.setattr(history, "snapshots", _commits)
    lines = reopened_lines(tmp_path, datetime(2026, 10, 17, tzinfo=UTC))
    assert 'nemik_cards_reopened_24h{repo="alpha"} 2' in lines
