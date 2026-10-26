# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W987: a ratchet is behind when its fall over the last landings is below what it owes."""

from nemik.ratchetpace import BEHIND, OK, seed, verdict, window_fall

WINDOW = 2
FALLING = [10, 10, 8, 8, 6, 6, 4]


def test_a_ratchet_falling_at_its_own_pace_is_ok() -> None:
    """Two earlier windows fell 4 in all, so 2 each; the last fell 2: ok."""
    assert (window_fall(FALLING, WINDOW), seed(FALLING, WINDOW)) == (2, 2)
    assert verdict(FALLING, WINDOW, 0) == (OK, 2, 2)


def test_a_stalled_nonzero_ratchet_is_behind() -> None:
    """Nothing fell, yet the value is above zero: it owes at least one."""
    assert verdict([10] * 7, WINDOW, 0) == (BEHIND, 0, 1)


def test_a_ratchet_at_zero_owes_nothing() -> None:
    """Paid in full: nothing is owed however it fell before."""
    assert verdict([3, 2, 1, 0, 0], WINDOW, 0) == (OK, 1, 0)


def test_the_requirement_only_rises() -> None:
    """A prior requirement of 3 holds although the history now seeds 2."""
    assert verdict(FALLING, WINDOW, 3) == (BEHIND, 2, 3)


def test_a_ratchet_is_never_required_to_fall_more_than_it_holds() -> None:
    """nemik:W1105: panflute required 6 against a value of 1; it is clamped to the value."""
    assert verdict(FALLING, WINDOW, 5) == (BEHIND, 2, 4)  # the value is 4
    assert verdict([6, 6, 6, 6, 6, 1], WINDOW, 6) == (OK, 5, 1)
    assert verdict([6, 6, 6, 6, 6, 1], WINDOW, 6)[2] <= 1


def test_a_series_shorter_than_a_window_is_judged_on_the_floor() -> None:
    """Too short to fall over a window, so a nonzero ratchet is behind; an empty series is ok."""
    assert verdict([5, 4], WINDOW, 0) == (BEHIND, 0, 1)
    assert verdict([], WINDOW, 0) == (OK, 0, 0)
