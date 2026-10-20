# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W616, W617, W682: a stale working card is stalled, or its progress is invisible."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from rdflib import Graph

from nemik import history, stalled
from nemik.adapter import queue_graph
from nemik.stalled import FACTOR, findings, verdict

HOUR = 3600
INTERVAL = HOUR
NOW = 1_000_000_000


def test_a_fresh_card_is_ok() -> None:
    """Worked within FACTOR land intervals: nothing to say."""
    assert verdict(NOW, NOW - FACTOR * INTERVAL, [], INTERVAL) == "ok"


def test_stale_and_uncited_is_stalled() -> None:
    """Past the bound with no commit citing it since: it looks stalled."""
    worked = NOW - (FACTOR + 1) * INTERVAL
    assert verdict(NOW, worked, [worked - 5], INTERVAL) == "stalled"


def test_stale_with_commits_landing_is_invisible() -> None:
    """Past the bound, yet a commit citing it landed after its last activity."""
    worked = NOW - (FACTOR + 1) * INTERVAL
    assert verdict(NOW, worked, [worked + 60], INTERVAL) == "invisible"


def _queue(tmp_path: Path, stamp: str) -> Graph:
    """Read a queue whose W1 is working since a stamp.

    Args:
        tmp_path: A scratch directory.
        stamp: The card's last_worked time.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    card: dict[str, object] = {
        "symbol": "W1",
        "title": "t",
        "status": "working",
        "last_worked": stamp,
    }
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/a",
        "counter": 1,
        "residue": residue,
        "waypoints": [card],
    }
    path = tmp_path / "a.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("a", path)


def _interval(repo: Path) -> int | None:
    """Answer a land interval of one hour.

    Args:
        repo: The repo's directory, unused.

    Returns:
        One hour in seconds.

    """
    del repo
    return INTERVAL


def _uncited(repo: Path, symbol: str) -> list[int] | None:
    """Answer that no commit cites the card.

    Args:
        repo: The repo's directory, unused.
        symbol: The card's symbol, unused.

    Returns:
        An empty list.

    """
    del repo, symbol
    return []


def _no_gate(repo: Path) -> set[str]:
    """Answer that no commit stack of the repo is queued or gating.

    Args:
        repo: The repo's directory, unused.

    Returns:
        An empty set.

    """
    del repo
    return set()


def _gating_w1(repo: Path) -> set[str]:
    """Answer that a commit stack carrying W1 is gating.

    Args:
        repo: The repo's directory, unused.

    Returns:
        {"W1"}.

    """
    del repo
    return {"W1"}


def test_the_finding_names_the_card_and_its_remedy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A card last worked ten hours before now, uncited, draws the stalled warning for repo a."""
    monkeypatch.setattr(history, "land_interval", _interval)
    monkeypatch.setattr(history, "citing_epochs", _uncited)
    monkeypatch.setattr(stalled, "in_gate", _no_gate)
    merged = _queue(tmp_path, "2026-10-17T00:00:00Z")
    now = int(datetime(2026, 10, 17, 10, tzinfo=UTC).timestamp())
    rows = findings(tmp_path, merged, now)
    assert [sym for sym, _ in rows["a"]] == ["W1"]
    assert "looks stalled" in rows["a"][0][1]


def _zero_interval(repo: Path) -> int:
    """Answer a learned land interval of zero: stacked commits that landed in one instant.

    Args:
        repo: The repo's directory, unused.

    Returns:
        0.

    """
    del repo
    return 0


def test_a_land_interval_under_the_floor_judges_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A zero interval would make every working card stale, so the shape skips the repo."""
    monkeypatch.setattr(history, "land_interval", _zero_interval)
    monkeypatch.setattr(history, "citing_epochs", _uncited)
    monkeypatch.setattr(stalled, "in_gate", _no_gate)
    merged = _queue(tmp_path, "2026-10-17T09:59:00Z")
    now = int(datetime(2026, 10, 17, 10, tzinfo=UTC).timestamp())
    assert findings(tmp_path, merged, now) == {}


def test_a_card_in_the_commit_gate_is_never_called_stalled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The same stale card, with a gating stack that names it, draws nothing."""
    monkeypatch.setattr(history, "land_interval", _interval)
    monkeypatch.setattr(history, "citing_epochs", _uncited)
    monkeypatch.setattr(stalled, "in_gate", _gating_w1)
    merged = _queue(tmp_path, "2026-10-17T00:00:00Z")
    now = int(datetime(2026, 10, 17, 10, tzinfo=UTC).timestamp())
    assert findings(tmp_path, merged, now) == {}
