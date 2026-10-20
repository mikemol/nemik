# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W747: the lead times and open ages a forecast is made from."""

from nemik.climate import leads_by_repo, open_ages

SHA = "abc123"
DAY = "2026-10-%02dT00:00:00+00:00"


def _at(day: int) -> str:
    return DAY % day


def _events() -> list[tuple[str, str, str, str, str, str]]:
    """List events: W1 minted day 1, done day 4; W2 minted day 2, still open; W3 never minted.

    Returns:
        The events.

    """
    return [
        ("a:W1", _at(1), "card", "", "minted", SHA),
        ("a:W1", _at(1), "status", "", "ready", SHA),
        ("a:W2", _at(2), "card", "", "minted", SHA),
        ("a:W2", _at(2), "status", "", "ready", SHA),
        ("a:W1", _at(4), "status", "ready", "done", SHA),
        ("a:W3", _at(3), "status", "", "done", SHA),
    ]


def test_the_leads_are_mint_to_first_done_for_cards_whose_mint_was_seen() -> None:
    """W1 took 3 days; W3 was done but its mint was never seen, so it has no lead."""
    assert leads_by_repo(_events(), _at(10)) == {"a": [3.0]}


def test_a_card_done_after_the_moment_has_no_lead_yet() -> None:
    """At day 3 W1 is still open."""
    assert leads_by_repo(_events(), _at(3)) == {}


def test_the_open_ages_are_days_since_mint_for_cards_still_open() -> None:
    """At day 6: W1 is done, W3 never minted; W2 is 4 days old."""
    assert open_ages(_events(), _at(6)) == {"a:W2": 4.0}
    assert open_ages(_events(), _at(3)) == {"a:W1": 2.0, "a:W2": 1.0}
