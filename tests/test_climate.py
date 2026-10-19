# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W746: the climate is a repo's activity over a window, counted from its events."""

from nemik.climate import climate_of, levels_at

SHA = "abc123"
DAY = "2026-10-%02dT00:00:00+00:00"
TOLERANCE = 1e-6


def _at(day: int) -> str:
    return DAY % day


def test_counts_and_lead_times_over_a_window() -> None:
    """W1 minted day 1, done day 3; W2 minted day 2, done day 6; W3 minted, then dropped."""
    events = [
        ("a:W1", _at(1), "card", "", "minted", SHA),
        ("a:W2", _at(2), "card", "", "minted", SHA),
        ("a:W1", _at(3), "status", "ready", "done", SHA),
        ("a:W3", _at(4), "card", "", "minted", SHA),
        ("a:W3", _at(5), "card", "ready", "dropped", SHA),
        ("a:W2", _at(6), "status", "ready", "done", SHA),
    ]
    got = climate_of(events, _at(1), _at(11))["a"]
    closed = len(("W1", "W2"))
    per_day = closed / 10
    lead = (2.0 + 4.0) / closed - 1.0
    assert got["minted"] == len(("W1", "W2", "W3"))
    assert got["done"] == closed
    assert got["dropped"] == 1
    assert abs(got["done_per_day"] - per_day) < TOLERANCE
    assert abs(got["lead_median_days"] - lead) < TOLERANCE
    assert abs(got["lead_p90_days"] - lead) < TOLERANCE
    assert got["leads"] == closed


def test_a_reopened_card_is_counted_and_a_close_before_the_window_is_not() -> None:
    """A card done before the window and reopened inside it is a reopen, not a close."""
    events = [
        ("a:W1", _at(1), "card", "", "minted", SHA),
        ("a:W1", _at(2), "status", "ready", "done", SHA),
        ("a:W1", _at(5), "status", "done", "ready", SHA),
        ("a:W1", _at(7), "status", "ready", "done", SHA),
    ]
    got = climate_of(events, _at(4), _at(11))["a"]
    assert got["reopened"] == 1
    assert not got["done"]
    assert not got["minted"]


def test_each_repo_is_counted_apart() -> None:
    """Stations name their repo before the colon."""
    events = [
        ("a:W1", _at(1), "card", "", "minted", SHA),
        ("b:W1", _at(1), "card", "", "minted", SHA),
        ("b:W2", _at(2), "card", "", "minted", SHA),
    ]
    got = climate_of(events, _at(1), _at(3))
    assert got["a"]["minted"] == 1
    assert got["b"]["minted"] == len(("W1", "W2"))


def test_levels_count_open_cards_by_state_at_a_moment() -> None:
    """Folded up to day 5: W1 ready, W2 blocked, W3 working, W4 done, W5 not yet minted."""
    events = [
        ("a:W1", _at(1), "card", "", "minted", SHA),
        ("a:W1", _at(1), "status", "", "ready", SHA),
        ("a:W2", _at(1), "card", "", "minted", SHA),
        ("a:W2", _at(1), "status", "", "blocked", SHA),
        ("a:W3", _at(2), "status", "", "working", SHA),
        ("a:W4", _at(2), "status", "", "ready", SHA),
        ("a:W4", _at(4), "status", "ready", "done", SHA),
        ("a:W5", _at(8), "status", "", "ready", SHA),
    ]
    got = levels_at(events, _at(5))["a"]
    opened = len(("W1", "W2", "W3"))
    assert got["open"] == opened
    assert got["ready"] == 1
    assert got["working"] == 1
    assert got["blocked"] == 1
    assert abs(got["blocked_share"] - 1 / opened) < TOLERANCE


def test_levels_of_a_repo_with_nothing_open_has_no_blocked_share() -> None:
    """Every card closed: the share is 0, not a division by zero."""
    events = [("a:W1", _at(1), "status", "", "done", SHA)]
    got = levels_at(events, _at(2))["a"]
    assert not got["open"]
    assert not got["blocked_share"]
