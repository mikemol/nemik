# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1144, W1146: the predicted net of a window, and the alert when reality parts from it."""

import pytest

from nemik.netforecast import (
    MINUTES_PER_DAY,
    alert_for,
    baseline_of,
    predicted_net,
    shortfall,
)

HOUR = 60
DAILY_NET = 24
PAST = [0.2, -0.1, 0.3, 0.1, 0.0, 0.2, -0.2, 0.1, 0.3, 0.2]
LEARNED = 0.3  # the ninetieth percentile of PAST by nearest rank


def test_a_whole_day_is_the_mean_daily_net() -> None:
    """Over a window of one day the prediction is the mean of the days before."""
    assert predicted_net([10, 20, 30], MINUTES_PER_DAY) == pytest.approx(20.0)


def test_a_window_scales_the_mean_by_its_length() -> None:
    """An hour of a day that nets 24 is predicted to net 1."""
    assert predicted_net([DAILY_NET], HOUR) == pytest.approx(1.0)


def test_a_net_that_adds_more_than_it_closes_predicts_a_negative() -> None:
    """The days before added more than they closed, so the window is predicted to."""
    assert predicted_net([-48, -48], HOUR) == pytest.approx(-2.0)


@pytest.mark.parametrize(
    ("nets", "minutes", "why"),
    [
        ([], HOUR, "no days to predict from"),
        ([1], 0, "a window has a length"),
        ([1], -5, "a window has a length"),
    ],
)
def test_no_history_or_no_window_is_refused_not_read_as_zero(
    nets: list[int], minutes: int, why: str
) -> None:
    """An unknown prediction raises; it is never a prediction of nothing."""
    with pytest.raises(ValueError, match=why):
        predicted_net(nets, minutes)


def test_the_shortfall_is_positive_when_the_window_did_worse() -> None:
    """Predicted one close and got none: a shortfall of one."""
    assert shortfall(1.0, 0) == pytest.approx(1.0)
    assert shortfall(1.0, 3) == pytest.approx(-2.0)


def test_the_baseline_is_learned_from_the_past_windows() -> None:
    """The ninetieth percentile, nearest rank, of the shortfalls already seen."""
    assert baseline_of(PAST) == pytest.approx(LEARNED)


def test_the_alert_fires_on_a_window_that_netted_nothing_against_a_close() -> None:
    """The 2026-10-27 replay: a predicted net of 1.0 and a realized +0 is a shortfall of 1.0."""
    said = alert_for(1.0, 0, PAST)
    assert said.startswith("misprediction: net +0 against a predicted +1.0")


def test_the_alert_is_silent_for_a_window_that_met_its_prediction() -> None:
    """A realized net at or above the prediction, or a small shortfall, says nothing."""
    assert not alert_for(1.0, 1, PAST)
    assert not alert_for(1.0, 3, PAST)
    assert not alert_for(1.2, 1, PAST)


def test_too_little_history_is_refused_not_read_as_a_quiet_baseline() -> None:
    """With fewer than three past windows there is no baseline to compare with."""
    with pytest.raises(ValueError, match="too few past windows"):
        alert_for(1.0, 0, [0.1, 0.2])
