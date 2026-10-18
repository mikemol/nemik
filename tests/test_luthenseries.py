# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W662: luthen's series snapshot is read, refused when stale, and classified."""

import json

import pytest

from nemik.luthenseries import NO_TICK, classify, parse

NOW = 1_000_000
BOUND = 900
COUNT = 7


def _snapshot(as_of: int = NOW - 60, version: int = 1) -> str:
    """Build a snapshot in the agreed shape.

    Args:
        as_of: When luthen wrote it, epoch seconds.
        version: The file's version.

    Returns:
        The file's text.

    """
    body = {
        "version": version,
        "as_of": as_of,
        "liveness": {
            "nemik": {
                "verdict": "live",
                "last_tick": NOW - 120,
                "history": [[NOW - 120, "live"], [NOW - 60, "live"]],
            },
            "quiet": {"verdict": "stale", "history": []},
        },
        "tokens": [{"repo": "nemik", "session": "u-1", "kind": "input", "value": 7}],
    }
    return json.dumps(body)


def test_a_fresh_snapshot_is_read() -> None:
    """Repos, their history and the token rows come through."""
    series = parse(_snapshot(), NOW, BOUND)
    assert series.as_of == NOW - 60
    assert series.repos["nemik"].last_tick == NOW - 120
    assert series.repos["nemik"].verdicts == ["live", "live"]
    assert series.repos["quiet"].last_tick == NO_TICK
    assert [(t.repo, t.kind, t.value) for t in series.tokens] == [("nemik", "input", 7)]


def test_the_verdict_in_force_at_a_time_and_a_repos_token_total() -> None:
    """History answers "what held then"; tokens sum by repo and kind."""
    series = parse(_snapshot(), NOW, BOUND)
    repo = series.repos["nemik"]
    assert not repo.verdict_at(NOW - 200)
    assert repo.verdict_at(NOW - 100) == "live"
    assert series.total("nemik", "input") == COUNT
    assert series.total("nemik", "output") == 0
    assert series.total("other", "input") == 0


def test_a_stale_snapshot_is_refused() -> None:
    """A producer that stopped must not read as live."""
    with pytest.raises(ValueError, match="as_of"):
        parse(_snapshot(as_of=NOW - BOUND - 1), NOW, BOUND)


def test_a_snapshot_from_the_future_is_refused() -> None:
    """A clock ahead of ours is no evidence of life."""
    with pytest.raises(ValueError, match="as_of"):
        parse(_snapshot(as_of=NOW + 1), NOW, BOUND)


def test_an_unversioned_snapshot_is_refused() -> None:
    """Only version 1 is understood."""
    with pytest.raises(ValueError, match="version"):
        parse(_snapshot(version=2), NOW, BOUND)


def test_a_repo_with_nothing_ready_is_idle_whatever_its_ticks() -> None:
    """No workable card, no debt: idle, even with no tick at all."""
    assert classify(NO_TICK, NOW, 0) == "idle"
    assert classify(NOW - 10, NOW, 0) == "idle"


def test_a_ticking_repo_with_work_is_awake_and_a_silent_one_is_asleep() -> None:
    """The bound is the loop's interval plus half again."""
    assert classify(NOW - 600, NOW, 3) == "awake"
    assert classify(NOW - 2701, NOW, 3) == "asleep"
    assert classify(NO_TICK, NOW, 3) == "asleep"
