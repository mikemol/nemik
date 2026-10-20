# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W748: the Brier score, and the rule that no lead finer than the truth's grain is scored."""

from nemik.verify import brier, scorable

TOLERANCE = 1e-9


def test_a_perfect_forecast_scores_zero_and_a_certain_wrong_one_scores_one() -> None:
    """Chance 1 for a done card and 0 for an undone one is perfect; the reverse is worst."""
    assert not brier([(1.0, True), (0.0, False)])
    assert abs(brier([(1.0, False), (0.0, True)]) - 1.0) < TOLERANCE


def test_always_saying_one_half_scores_a_quarter() -> None:
    """The no-skill score, whatever happened."""
    assert abs(brier([(0.5, True), (0.5, False)]) - 0.25) < TOLERANCE


def test_no_forecasts_score_zero() -> None:
    """Nothing was forecast, so nothing was wrong."""
    assert not brier([])


def test_a_lead_finer_than_the_grain_is_not_scored() -> None:
    """Against commit-grain truth of one day, +1d and longer are scored and half a day is not."""
    assert scorable(1.0, 1.0)
    assert scorable(3.0, 1.0)
    assert not scorable(0.5, 1.0)
