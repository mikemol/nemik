# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W747: the forecast rows for the open cards at one moment."""

from nemik.history import forecast_rows

SHA = "abc123"
DAY = "2026-10-%02dT00:00:00+00:00"


def _at(day: int) -> str:
    return DAY % day


def test_each_open_card_gets_a_row_per_lead_from_its_repos_lead_times() -> None:
    """W1 took 2 days; open W2, 1 day old at day 4, has half of a 1-day-and-up lead: done by +3d."""
    events = [
        ("a:W1", _at(1), "card", "", "minted", SHA),
        ("a:W1", _at(3), "status", "ready", "done", SHA),
        ("a:W2", _at(3), "card", "", "minted", SHA),
        ("a:W2", _at(3), "status", "", "ready", SHA),
    ]
    rows = forecast_rows(events, _at(4))
    assert [r[1:3] for r in rows] == [
        ["a:W2", "+1d"],
        ["a:W2", "+3d"],
        ["a:W2", "+7d"],
    ]
    assert {r[3] for r in rows} == {"1"}


def test_with_no_card_open_there_are_no_rows() -> None:
    """Every card done: nothing to forecast."""
    events = [
        ("a:W1", _at(1), "card", "", "minted", SHA),
        ("a:W1", _at(3), "status", "ready", "done", SHA),
    ]
    assert forecast_rows(events, _at(4)) == []
