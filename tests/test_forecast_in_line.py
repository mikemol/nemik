# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W831: a card's forecast chance is capped by its place in its repo's line."""

import pytest

from nemik.climate import finish_rates
from nemik.forecastshingle import in_line, issue_in_line

CHANCE = 0.99
RATE = 2.0
NINE_AHEAD = 9
EXPECTED = 0.198
HORIZONS = [1.0, 3.0]
LEADS = [1.0, 2.0, 5.0]
QUARTER = 0.25
# (station, stamp, field, before, now, extra): a card minted on day 1 and done on day 3
EVENTS = [
    ("r:W1", "2026-10-01T00:00:00+00:00", "card", "", "minted", ""),
    ("r:W1", "2026-10-03T00:00:00+00:00", "status", "ready", "done", ""),
    ("r:W2", "2026-10-02T00:00:00+00:00", "card", "", "minted", ""),
]


def test_the_front_of_the_line_keeps_its_chance() -> None:
    """With nothing ahead and a repo that finishes more than a card a horizon, the cap is 1."""
    assert in_line(CHANCE, RATE, 0, 1.0) == pytest.approx(CHANCE)


def test_a_card_far_back_gets_the_share_of_the_line_the_horizon_reaches() -> None:
    """Two a day over one day against nine ahead reaches 2 / 10 of the line: 0.99 becomes 0.198."""
    assert in_line(CHANCE, RATE, NINE_AHEAD, 1.0) == pytest.approx(EXPECTED)


def test_a_repo_that_finishes_nothing_gives_no_chance() -> None:
    """A rate of zero reaches none of the line."""
    assert in_line(CHANCE, 0.0, 0, 1.0) == pytest.approx(0.0)


def test_a_longer_horizon_reaches_further_back() -> None:
    """Three days reach three times the line one day does, until the whole line is reached."""
    one = in_line(1.0, RATE, NINE_AHEAD, 1.0)
    three = in_line(1.0, RATE, NINE_AHEAD, 3.0)
    assert three == pytest.approx(3 * one)


def test_issue_in_line_caps_each_horizon_by_its_own_reach() -> None:
    """The lead-time chance at each horizon is scaled by that horizon's reach into the line."""
    got = issue_in_line(LEADS, 0.0, HORIZONS, RATE, NINE_AHEAD)
    assert list(got) == ["+1d", "+3d"]
    # one lead of three is within a day (1/3), all but the 5-day one within three (2/3)
    assert got["+1d"] == pytest.approx(1 / 3 * 0.2)
    assert got["+3d"] == pytest.approx(2 / 3 * 0.6)


def test_a_repos_finish_rate_is_its_done_cards_over_the_days_seen() -> None:
    """One card done in the four days from the first event to the moment is a quarter a day."""
    rates = finish_rates(EVENTS, "2026-10-05T00:00:00+00:00")
    assert rates == {"r": pytest.approx(QUARTER)}
    assert finish_rates([], "2026-10-05T00:00:00+00:00") == {}
