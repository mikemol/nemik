# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W753: the waits summary gives the count, median and ninetieth percentile per status."""

from nemik.history import waits

SHA = "abc123"
DAY = "2026-10-%02dT00:00:00+00:00"


def _at(day: int) -> str:
    return DAY % day


def test_waits_summarize_each_status_by_count_and_quantiles() -> None:
    """Two ready stints of 2 and 4 days, one blocked stint of 1 day."""
    events = [
        ("a:W1", _at(1), "status", "", "ready", SHA),
        ("a:W1", _at(3), "status", "ready", "blocked", SHA),
        ("a:W1", _at(4), "status", "blocked", "ready", SHA),
        ("a:W1", _at(8), "status", "ready", "done", SHA),
    ]
    got = waits(events)
    assert got["ready"] == {"n": 2, "median_days": 4.0, "p90_days": 2.0}
    assert got["blocked"] == {"n": 1, "median_days": 1.0, "p90_days": 1.0}
