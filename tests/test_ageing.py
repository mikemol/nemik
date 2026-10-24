# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1001: the learned bound and a ready card's overdue count."""

from nemik.ageing import NO_BOUND, learned_bound, overdue

DAY = 86400
TEN = [d * DAY for d in (1, 2, 3, 4, 5, 6, 7, 8, 9, 100)]


def test_the_bound_is_the_ninetieth_percentile_and_needs_ten_spans() -> None:
    """Ten spans: the 9th smallest. Nine: none learned. Zeros: none."""
    assert learned_bound(TEN) == 9 * DAY
    assert learned_bound(TEN[:9]) == NO_BOUND
    assert learned_bound([0] * 10) == NO_BOUND


def test_a_card_within_two_bounds_is_not_overdue() -> None:
    """The grace is two bounds; with no bound nothing is overdue."""
    assert overdue(2 * DAY - 1, DAY) == 0
    assert overdue(5 * DAY, NO_BOUND) == 0


def test_overdue_rises_by_one_per_bound_after_the_grace() -> None:
    """One at two bounds, then one more each further bound."""
    got = [overdue(n * DAY, DAY) for n in (2, 3, 7)]
    assert got == [1, 2, 6]
