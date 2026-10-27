# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W987: a ratchet is behind when its fall over the last landings is below what it owes."""

from nemik.ratchetpace import (
    BEHIND,
    NO_HORIZON,
    OK,
    horizon,
    seed,
    verdict,
    window_fall,
)

WINDOW = 2
WIDE = 10  # the pace's real window of landings
FELL = 16  # 18 down to 2
FALLING = [14, 14, 12, 12, 10, 10, 8, 8, 6, 6, 4]
# one window that fell 90 in a single landing, then steady: a burst, not a rate (nemik:W1158)
BURST = [100, 100, 10, 10, 10, 10, 10, 10, 10, 10, 9, 9]
# nemik's mypy series after its declared re-baseline: one whole earlier window, holding W1124's 104
NEMIK_MYPY = [5747, 5744, *[5640] * 6, *[5638] * 11, 5636, 5634, 5631]
OWED_BEFORE = 2  # what the pace stated for it before the seed turned on
SLOWING = [10, 10, 10, 10, 9, 7]
SLOWING_HORIZON = 5


def test_a_ratchet_falling_at_its_own_pace_is_ok() -> None:
    """Four earlier windows fell 2 each, so the median is 2; the last fell 2: ok."""
    assert (window_fall(FALLING, WINDOW), seed(FALLING, WINDOW)) == (2, 2)
    assert verdict(FALLING, WINDOW, 0) == (OK, 2, 2)


def test_one_burst_is_not_a_rate() -> None:
    """The median of the earlier windows' falls ignores the one that held the burst."""
    assert seed(BURST, WINDOW) == 0
    assert verdict(BURST, WINDOW, 0)[2] == 1


def test_a_single_earlier_window_seeds_nothing() -> None:
    """nemik:W1158: 22 samples after a declared step hold one whole earlier window, fall 109.

    The mean of that one window was a requirement of 109 a window, which only rises; fewer than
    three whole windows is not a trend, so the seed is 0 and the floor of one stands.
    """
    assert seed(NEMIK_MYPY, WIDE) == 0
    assert verdict(NEMIK_MYPY, WIDE, OWED_BEFORE)[2] == OWED_BEFORE


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


def test_a_series_shorter_than_a_window_is_judged_on_the_fall_it_has_seen() -> None:
    """A short series that fell the floor is ok, one that stalled or rose is behind."""
    assert verdict([5, 4], WINDOW, 0) == (OK, 1, 1)
    assert verdict([5, 5], WINDOW, 0) == (BEHIND, 0, 1)
    assert verdict([4, 5], WINDOW, 0) == (BEHIND, -1, 1)
    assert verdict([], WINDOW, 0) == (OK, 0, 0)


def test_a_ratchet_rebaselined_a_few_landings_ago_that_has_paid_since_is_ok() -> None:
    """nemik:W1155: linux-sources' letter-quotes from its declared step, 18 to 2 over nine samples.

    The window is ten landings and the history since the declared step is nine samples, which
    read observed 0 and behind although the value fell by sixteen.
    """
    since_the_step = [18, 18, 18, 13, 12, 11, 9, 5, 2]
    assert window_fall(since_the_step, WIDE) == FELL
    assert verdict(since_the_step, WIDE, 0) == (OK, FELL, 1)


def test_the_horizon_is_the_value_over_the_fall_per_landing() -> None:
    """W1112: 4 left, 2 fell over 2 landings (1 a landing): 4 landings to zero, rounded up."""
    assert horizon(FALLING, WINDOW) == FALLING[-1]
    # 7 left, 3 fell over 2 landings: 4.67 landings, rounded up
    assert horizon(SLOWING, WINDOW) == SLOWING_HORIZON
    assert horizon([10] * 7, WINDOW) == NO_HORIZON
    assert horizon([3, 2, 1, 0, 0], WINDOW) == 0
    # a series shorter than the window: 4 left, 1 fell over the one landing seen
    assert horizon([5, 4], WINDOW) == FALLING[-1]
    assert horizon([5, 5], WINDOW) == NO_HORIZON
