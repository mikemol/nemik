# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W747: the chance a card is done within a horizon, from the lead times of past cards."""

from nemik.forecastshingle import done_by, issue

TOLERANCE = 1e-9
LEADS = [1.0, 2.0, 4.0, 8.0]
DAYS = [1.0, 3.0, 7.0]


def test_a_new_card_is_done_within_a_horizon_as_often_as_past_ones_were() -> None:
    """Age 0: half the leads end within 2 days (1 and 2), a quarter within 1."""
    assert abs(done_by(LEADS, 0.0, 2.0) - 0.5) < TOLERANCE
    assert abs(done_by(LEADS, 0.0, 1.0) - 0.25) < TOLERANCE


def test_an_older_card_is_judged_against_the_leads_that_outlasted_its_age() -> None:
    """At age 2 only the leads 4 and 8 remain; one of them ends within 3 more days."""
    assert abs(done_by(LEADS, 2.0, 3.0) - 0.5) < TOLERANCE


def test_with_no_longer_lead_the_chance_is_a_floor_of_zero() -> None:
    """A card older than every past lead, or with no history, has no evidence of finishing."""
    assert not done_by(LEADS, 9.0, 7.0)
    assert not done_by([], 0.0, 7.0)


def test_one_issue_has_a_chance_at_each_horizon_and_they_do_not_fall() -> None:
    """The chance within a longer horizon is at least that within a shorter one."""
    got = issue(LEADS, 0.0, DAYS)
    assert list(got) == ["+1d", "+3d", "+7d"]
    assert got["+1d"] <= got["+3d"] <= got["+7d"]
