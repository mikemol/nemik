# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W760: the reliability of forecast chances, binned."""

from nemik.verify import reliability

TOLERANCE = 1e-9
LOW = [(0.1, False), (0.2, True), (0.3, False), (0.4, False)]
HIGH = [(0.8, True), (1.0, True)]


def test_each_bin_gives_its_mean_chance_the_share_that_happened_and_the_count() -> None:
    """Four forecasts in the low half (one happened) and two in the high (both happened)."""
    low, high = reliability([*LOW, *HIGH], 2)
    assert abs(low[0] - 0.25) < TOLERANCE
    assert abs(low[1] - 0.25) < TOLERANCE
    assert low[2] == len(LOW)
    assert abs(high[0] - 0.9) < TOLERANCE
    assert abs(high[1] - 1.0) < TOLERANCE
    assert high[2] == len(HIGH)


def test_an_empty_bin_is_left_out_and_no_bins_gives_nothing() -> None:
    """All chances in the top bin: one row; zero bins: none; no forecasts: none."""
    assert len(reliability([(0.9, True)], 4)) == 1
    assert reliability([(0.9, True)], 0) == []
    assert reliability([], 4) == []
