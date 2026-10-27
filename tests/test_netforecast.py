# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1144, W1146, W1151, W1145: the predicted net of a window and the alert on a miss."""

import pytest

from nemik.netforecast import (
    MINUTES_PER_DAY,
    alert_for,
    baseline_of,
    predicted_net,
    replay_row,
    shortfall,
)

HOUR = 60
DAILY_NET = 24
PAST = [0.2, -0.1, 0.3, 0.1, 0.0, 0.2, -0.2, 0.1, 0.3, 0.2]
LEARNED = 0.3  # the ninetieth percentile of the absolute values of PAST by nearest rank
DAILY = [-48, -48, -48]  # a fleet adding two cards an hour more than it closes
QUIET_PAST = [-2, -2, -2, -2]  # earlier hours that netted what was predicted


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
    assert baseline_of([abs(past) for past in PAST]) == pytest.approx(LEARNED)


def test_the_alert_fires_on_a_window_that_did_worse_than_predicted() -> None:
    """The fleet wandering: a predicted net of 1.0 and a realized +0."""
    said = alert_for(1.0, 0, PAST)
    assert said.startswith("misprediction: net +0 against a predicted +1.0")
    assert "look why" in said


def test_the_alert_fires_on_a_window_that_did_better_than_predicted() -> None:
    """The model wrong: a predicted net of 1.0 and a realized +3 is as much a miss."""
    said = alert_for(1.0, 3, PAST)
    assert said.startswith("misprediction: net +3 against a predicted +1.0")
    assert "fix it" in said


def test_the_alert_is_silent_for_a_window_that_met_its_prediction() -> None:
    """A realized net at the prediction, or within the usual miss, says nothing."""
    assert not alert_for(1.0, 1, PAST)
    assert not alert_for(1.2, 1, PAST)
    assert not alert_for(0.8, 1, PAST)


def test_too_little_history_is_refused_not_read_as_a_quiet_baseline() -> None:
    """With fewer than three past windows there is no baseline to compare with."""
    with pytest.raises(ValueError, match="too few past windows"):
        alert_for(1.0, 0, [0.1, 0.2])


def test_a_replay_that_met_its_prediction_prints_one_line() -> None:
    """Predicted -2.0 an hour and netted -2: the line, and no alert."""
    line = replay_row(DAILY, HOUR, QUIET_PAST, -2)
    assert line == "replay: predicted -2.0, realized -2, shortfall +0.0"


def test_a_replay_that_missed_prints_the_alert_beneath() -> None:
    """Predicted -2.0 and netted +4: the model expected worse than happened."""
    first, second = replay_row(DAILY, HOUR, QUIET_PAST, 4).split("\n")
    assert first == "replay: predicted -2.0, realized +4, shortfall -6.0"
    assert second.startswith("misprediction:")
