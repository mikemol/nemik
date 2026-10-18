# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W662, W352: luthen's series snapshot is read, refused when stale, and read as states."""

import json

import pytest

from nemik.luthenseries import NO_TICK, parse, state_of, stranded

NOW = 1_000_000
BOUND = 900
COUNT = 7


def _snapshot(as_of: int = NOW - 60, version: int = 1) -> str:
    """Build a snapshot in the agreed shape, with luthen's three verdicts.

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
                "verdict": "ok",
                "last_tick": NOW - 120,
                "history": [[NOW - 120, "ok"], [NOW - 60, "ok"]],
            },
            "quiet": {"verdict": "stale", "history": []},
            "gone": {"verdict": "dormant", "history": []},
        },
        "tokens": [{"repo": "nemik", "session": "u-1", "kind": "input", "value": 7}],
    }
    return json.dumps(body)


def test_a_fresh_snapshot_is_read() -> None:
    """Repos, their history and the token rows come through."""
    series = parse(_snapshot(), NOW, BOUND)
    assert series.as_of == NOW - 60
    assert series.repos["nemik"].last_tick == NOW - 120
    assert series.repos["nemik"].verdicts == ["ok", "ok"]
    assert series.repos["quiet"].last_tick == NO_TICK
    assert [(t.repo, t.kind, t.value) for t in series.tokens] == [("nemik", "input", 7)]


def test_the_verdict_in_force_at_a_time_and_a_repos_token_total() -> None:
    """History answers "what held then"; tokens sum by repo and kind."""
    series = parse(_snapshot(), NOW, BOUND)
    repo = series.repos["nemik"]
    assert not repo.verdict_at(NOW - 200)
    assert repo.verdict_at(NOW - 100) == "ok"
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


def test_luthens_verdicts_read_as_wake_reads_them() -> None:
    """Verdict ok is awake, dormant is asleep, and any other string is idle, not an error."""
    assert state_of("ok") == "awake"
    assert state_of("dormant") == "asleep"
    assert state_of("stale") == "idle"
    assert state_of("a-verdict-luthen-adds-later") == "idle"


def test_the_repos_with_work_that_are_not_awake_are_listed_asleep_first() -> None:
    """Asleep ones, then idle ones; an awake repo, or one with nothing ready, is not listed."""
    series = parse(_snapshot(), NOW, BOUND)
    ready = {"nemik": 5, "quiet": 2, "gone": 3}
    assert stranded(series, ready) == ["gone", "quiet"]
    assert stranded(series, {"nemik": 5, "quiet": 0, "gone": 0}) == []
