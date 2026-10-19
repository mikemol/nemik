# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W746: the levels over time are the levels at evenly spaced moments."""

from nemik.climate import levels_series

SHA = "abc123"
DAY = "2026-10-%02dT00:00:00+00:00"


def _at(day: int) -> str:
    return DAY % day


def test_the_series_walks_from_start_to_end_inclusive() -> None:
    """A card ready on day 2 and done on day 4 is open on days 2 and 3 only."""
    events = [
        ("a:W1", _at(2), "status", "", "ready", SHA),
        ("a:W1", _at(4), "status", "ready", "done", SHA),
    ]
    series = levels_series(events, _at(1), _at(5), 1.0)
    assert [moment for moment, _ in series] == [_at(d) for d in range(1, 6)]
    opened = [levels.get("a", {}).get("open", 0.0) for _, levels in series]
    assert opened == [0.0, 1.0, 1.0, 0.0, 0.0]


def test_a_step_that_is_not_positive_gives_only_the_start() -> None:
    """No step would never end; the series is its first moment."""
    series = levels_series([], _at(1), _at(5), 0.0)
    assert [moment for moment, _ in series] == [_at(1)]
