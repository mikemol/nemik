# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1144: the predicted net of a window scales the mean daily net, and never guesses zero."""

import pytest

from nemik.netforecast import MINUTES_PER_DAY, predicted_net

HOUR = 60
DAILY_NET = 24


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
