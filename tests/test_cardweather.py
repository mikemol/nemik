# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W745: the weather is each card's state folded out of its events."""

from nemik.cardweather import weather_of

SHA = "abc123"


def test_the_latest_status_and_when_it_began_win() -> None:
    """A minted card moved ready, then blocked on an agent, then done."""
    events = [
        ("a:W1", "2026-10-01T00:00:00+00:00", "card", "", "minted", SHA),
        ("a:W1", "2026-10-01T00:00:00+00:00", "status", "", "ready", SHA),
        ("a:W1", "2026-10-02T00:00:00+00:00", "status", "ready", "blocked", SHA),
        ("a:W1", "2026-10-02T00:00:00+00:00", "blocked_kind", "", "agent", SHA),
        ("a:W1", "2026-10-02T00:00:00+00:00", "blocked_on", "", "mtools:W9", SHA),
        ("a:W1", "2026-10-03T00:00:00+00:00", "status", "blocked", "done", SHA),
        ("a:W1", "2026-10-03T00:00:00+00:00", "blocked_on", "mtools:W9", "", SHA),
    ]
    got = weather_of(events)["a:W1"]
    assert got["status"] == "done"
    assert got["status_since"] == "2026-10-03T00:00:00+00:00"
    assert got["blocked_kind"] == "agent"
    assert not got["blocked_on"]


def test_stations_are_kept_apart_and_a_dropped_card_ends_dropped() -> None:
    """Two cards fold separately; enables changes leave the weather alone."""
    events = [
        ("a:W1", "2026-10-01T00:00:00+00:00", "status", "", "ready", SHA),
        ("a:W2", "2026-10-01T00:00:00+00:00", "status", "", "ready", SHA),
        ("a:W2", "2026-10-02T00:00:00+00:00", "enables", "", "W1", SHA),
        ("a:W2", "2026-10-03T00:00:00+00:00", "card", "ready", "dropped", SHA),
    ]
    got = weather_of(events)
    assert got["a:W1"]["status"] == "ready"
    assert got["a:W2"]["status"] == "dropped"
    assert got["a:W2"]["status_since"] == "2026-10-03T00:00:00+00:00"
