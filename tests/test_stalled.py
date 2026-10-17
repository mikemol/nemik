# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W616, W617: a stale working card is stalled, or its progress is invisible."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from rdflib import Graph

from nemik import history
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


def test_the_finding_names_the_card_and_its_remedy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A card last worked ten hours before now, uncited, draws the stalled warning for repo a."""
    monkeypatch.setattr(history, "land_interval", _interval)
    monkeypatch.setattr(history, "citing_epochs", _uncited)
    merged = _queue(tmp_path, "2026-10-17T00:00:00Z")
    now = int(datetime(2026, 10, 17, 10, tzinfo=UTC).timestamp())
    rows = findings(tmp_path, merged, now)
    assert [sym for sym, _ in rows["a"]] == ["W1"]
    assert "looks stalled" in rows["a"][0][1]
