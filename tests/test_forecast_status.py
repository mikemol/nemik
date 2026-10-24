# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W966: a blocked card takes no place in a repo's line and is capped by blocked stints."""

import pytest

from nemik.climate import open_status
from nemik.forecastshingle import issue_blocked, stint_share
from nemik.history import forecast_rows

SHA = "abc123"
DAY = "2026-10-%02dT00:00:00+00:00"
HORIZONS = [1.0, 3.0, 7.0]
STINTS = [0.5, 2.0, 10.0]
ONE_THIRD = 1 / 3
TWO_THIRDS = 2 / 3


def _at(day: int) -> str:
    return DAY % day


def test_the_share_of_stints_that_ended_within_a_horizon() -> None:
    """One of three stints ended within a day, two within seven; with none, a floor of zero."""
    assert stint_share(STINTS, 1.0) == pytest.approx(ONE_THIRD)
    assert stint_share(STINTS, 7.0) == pytest.approx(TWO_THIRDS)
    assert stint_share([], 7.0) == pytest.approx(0.0)


def test_a_blocked_cards_chance_is_capped_by_how_blocked_stints_end() -> None:
    """The lead-time chance at +7d is 1.0, but only two thirds of blocked stints end by then."""
    got = issue_blocked([5.0], 1.0, HORIZONS, STINTS)
    assert got["+1d"] == pytest.approx(0.0)
    assert got["+3d"] == pytest.approx(0.0)
    assert got["+7d"] == pytest.approx(TWO_THIRDS)


def test_the_status_of_each_open_card_is_read_from_its_events() -> None:
    """Ready, blocked and minted-with-no-status cards are named; a done one is left out."""
    events = [
        ("a:W1", _at(1), "card", "", "minted", SHA),
        ("a:W1", _at(2), "status", "", "ready", SHA),
        ("a:W2", _at(1), "card", "", "minted", SHA),
        ("a:W2", _at(2), "status", "ready", "blocked", SHA),
        ("a:W3", _at(1), "card", "", "minted", SHA),
        ("a:W4", _at(1), "card", "", "minted", SHA),
        ("a:W4", _at(2), "status", "", "done", SHA),
    ]
    assert open_status(events, _at(3)) == {
        "a:W1": "ready",
        "a:W2": "blocked",
        "a:W3": "",
    }


def _chance_of(rows: list[list[str]], station: str, lead: str) -> str:
    """Read a station's chance at a lead out of shingle rows.

    Returns:
        The chance text.

    """
    return next(r[4] for r in rows if r[1] == station and r[2] == lead)


def test_an_older_blocked_card_does_not_push_a_younger_ready_card_back() -> None:
    """With W2 (older) blocked, ready W3 stands first in line: as if W2 were absent."""
    done = [
        ("a:W1", _at(1), "card", "", "minted", SHA),
        ("a:W1", _at(4), "status", "ready", "done", SHA),
    ]
    ready = [
        ("a:W3", _at(5), "card", "", "minted", SHA),
        ("a:W3", _at(5), "status", "", "ready", SHA),
    ]
    blocked = [
        ("a:W2", _at(4), "card", "", "minted", SHA),
        ("a:W2", _at(4), "status", "", "blocked", SHA),
    ]
    alone = forecast_rows(done + ready, _at(7))
    behind_blocked = forecast_rows(done + blocked + ready, _at(7))
    assert _chance_of(behind_blocked, "a:W3", "+1d") == _chance_of(alone, "a:W3", "+1d")
    assert float(_chance_of(alone, "a:W3", "+1d")) > 0.0


def test_an_older_ready_card_still_pushes_a_younger_one_back() -> None:
    """The line is unchanged for cards that can start: a ready W2 ahead halves W3's chance."""
    done = [
        ("a:W1", _at(1), "card", "", "minted", SHA),
        ("a:W1", _at(4), "status", "ready", "done", SHA),
    ]
    younger = [
        ("a:W3", _at(5), "card", "", "minted", SHA),
        ("a:W3", _at(5), "status", "", "ready", SHA),
    ]
    older = [
        ("a:W2", _at(4), "card", "", "minted", SHA),
        ("a:W2", _at(4), "status", "", "ready", SHA),
    ]
    alone = float(_chance_of(forecast_rows(done + younger, _at(7)), "a:W3", "+1d"))
    behind = float(
        _chance_of(forecast_rows(done + older + younger, _at(7)), "a:W3", "+1d")
    )
    # the rows keep six significant figures, so halves agree to about one part in a million
    assert behind == pytest.approx(alone / 2, rel=1e-4)
