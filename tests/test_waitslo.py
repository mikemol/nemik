# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W700: the wait target is learned with the open waits counted, and says when it cannot."""

import pytest

from nemik.waitslo import BUDGET, burn, target_age


def _near(value: float, expected: float) -> bool:
    """Say whether two floats agree to rounding.

    Returns:
        True when `value` equals `expected` within pytest's tolerance.

    """
    return value == pytest.approx(expected)


def _answered(*ages: float) -> list[tuple[float, bool]]:
    """Build answered waits of the given ages.

    Returns:
        The rows, each (age, True).

    """
    return [(age, True) for age in ages]


def test_answered_waits_alone_give_their_ninetieth_percentile() -> None:
    """Ten answered waits, nine at one day and one at ten: nine in ten answered by day one."""
    rows = _answered(1, 1, 1, 1, 1, 1, 1, 1, 1, 10)
    assert _near(target_age(rows, BUDGET), 1.0)
    ladder = _answered(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    assert _near(target_age(ladder, BUDGET), 9.0)
    assert _near(target_age(ladder, 0.5), 5.0)


def test_open_waits_keep_the_target_from_being_learned() -> None:
    """Answered waits of one day look like a one-day target; twenty open 30-day waits say no."""
    answered = _answered(*([1.0] * 10))
    assert _near(target_age(answered, BUDGET), 1.0)
    with_open = answered + [(30.0, False)] * 20
    assert _near(target_age(with_open, BUDGET), -1.0)


def test_open_waits_that_are_young_do_not_hold_the_target_up() -> None:
    """Censored waits younger than the answered ones leave the at-risk set before they count."""
    rows = _answered(*([5.0] * 9)) + [(1.0, False)] * 3 + [(5.0, False)]
    assert _near(target_age(rows, 0.5), 5.0)


def test_no_rows_learn_nothing() -> None:
    """Without any wait there is no age to learn."""
    assert _near(target_age([], BUDGET), -1.0)


def test_burn_is_the_open_share_past_the_target_over_the_budget() -> None:
    """Of four open waits two are past a 9-day target: half, against a tenth, is five times over."""
    rows = [(1.0, False), (3.0, False), (20.0, False), (40.0, False), (2.0, True)]
    assert _near(burn(rows, 9.0, BUDGET), 5.0)
    assert _near(burn(rows, 100.0, BUDGET), 0.0)


def test_burn_without_a_target_is_not_zero() -> None:
    """A target that could not be learned reads -1, never a quiet 0 (the mutant returned 0)."""
    rows = [(30.0, False)] * 20 + _answered(1.0, 1.0)
    assert _near(burn(rows, -1.0, BUDGET), -1.0)


def test_burn_with_nothing_open_is_zero() -> None:
    """Only answered waits: nothing is spending the budget."""
    assert _near(burn(_answered(1.0, 2.0), 9.0, BUDGET), 0.0)
