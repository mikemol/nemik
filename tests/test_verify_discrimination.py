# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W965: a forecast is judged on whether it ranks the finishers above the rest."""

import pytest

from nemik.verify import UNDEFINED, discrimination, lead_report

BINS = 5
HALF = 0.5


def test_a_forecast_that_ranks_every_finisher_first_scores_one() -> None:
    """Finishers given higher chances than every other card: 1.0; the reverse: 0.0."""
    good = [(0.9, True), (0.8, True), (0.2, False), (0.1, False)]
    bad = [(0.1, True), (0.2, True), (0.8, False), (0.9, False)]
    assert discrimination(good) == pytest.approx(1.0)
    assert discrimination(bad) == pytest.approx(0.0)


def test_the_base_rate_for_every_card_ties_and_scores_one_half() -> None:
    """A forecast that says the same number for all ranks nothing: ties count half."""
    flat = [(0.02, False)] * 98 + [(0.02, True)] * 2
    assert discrimination(flat) == pytest.approx(HALF)


def test_a_ranking_forecast_scores_above_a_flat_one() -> None:
    """The same four cards: a forecast that ranks them scores 1.0, one that does not 0.5."""
    flat = [(0.5, True), (0.5, False), (0.5, True), (0.5, False)]
    ranked = [(0.9, True), (0.9, True), (0.1, False), (0.1, False)]
    assert discrimination(flat) == pytest.approx(HALF)
    assert discrimination(ranked) == pytest.approx(1.0)


def test_with_nothing_to_rank_it_is_undefined() -> None:
    """No finisher, or only finishers, gives the sentinel, not a made-up number."""
    assert discrimination([(0.1, False), (0.2, False)]) == pytest.approx(UNDEFINED)
    assert discrimination([(0.9, True)]) == pytest.approx(UNDEFINED)
    assert discrimination([]) == pytest.approx(UNDEFINED)


def test_a_lead_report_carries_it() -> None:
    """The score report has a discrimination entry beside Brier and the skills."""
    pairs = [(0.9, True), (0.1, False), (0.2, False), (0.3, True)]
    report = lead_report(pairs, BINS)
    assert report["discrimination"] == pytest.approx(discrimination(pairs))
