# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W748: count error, the two reference forecasts, and skill against them."""

from nemik.verify import climatology_brier, mae, persistence_brier, skill

TOLERANCE = 1e-9


def test_the_count_error_is_the_mean_absolute_distance() -> None:
    """Expected 3 against 5 and 4 against 4: one error of 2 over two forecasts."""
    assert abs(mae([(3.0, 5.0), (4.0, 4.0)]) - 1.0) < TOLERANCE
    assert not mae([])


def test_persistence_scores_the_share_of_cards_that_did_finish() -> None:
    """Saying nothing finishes is wrong for each card that did: 1 of 4 gives 0.25."""
    assert abs(persistence_brier([True, False, False, False]) - 0.25) < TOLERANCE
    assert not persistence_brier([False, False])


def test_climatology_scores_the_variance_of_the_outcomes() -> None:
    """The base rate 0.5 over two outcomes scores 0.25; all alike scores 0."""
    assert abs(climatology_brier([True, False]) - 0.25) < TOLERANCE
    assert not climatology_brier([True, True])
    assert not climatology_brier([])


def test_skill_is_the_share_of_the_reference_error_removed() -> None:
    """Half the reference score is 0.5, equal is 0, worse is below 0, a perfect reference 0."""
    assert abs(skill(0.1, 0.2) - 0.5) < TOLERANCE
    assert not skill(0.2, 0.2)
    assert skill(0.3, 0.2) < 0
    assert not skill(0.1, 0.0)
