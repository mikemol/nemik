# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W761: one lead's forecasts judged against the two references, and the shingle report."""

from nemik.history import score_report
from nemik.verify import lead_report

TOLERANCE = 1e-9
SHA = "abc123"
DAY = "2026-10-%02dT00:00:00+00:00"
BINS = 2


def _at(day: int) -> str:
    return DAY % day


def test_a_lead_report_has_the_references_the_skill_and_the_bins() -> None:
    """Four forecasts, one happened, all said 0.25: persistence 0.25, climatology 0.1875."""
    pairs = [(0.25, True), (0.25, False), (0.25, False), (0.25, False)]
    got = lead_report(pairs, BINS)
    assert got["n"] == len(pairs)
    assert abs(got["persistence"] - 0.25) < TOLERANCE
    assert abs(got["climatology"] - 0.1875) < TOLERANCE
    assert abs(got["brier"] - 0.1875) < TOLERANCE
    assert abs(got["skill_climatology"]) < TOLERANCE
    assert abs(got["bin0_share"] - 0.25) < TOLERANCE


def test_the_shingle_report_is_per_lead_and_leaves_out_what_cannot_be_judged() -> None:
    """W1 done day 3, forecast day 1 at +3d with 0.5: judged; +0.5d is finer than a day."""
    rows = [
        [_at(1), "a:W1", "+3d", "0", "0.5"],
        [_at(1), "a:W1", "+0.5d", "0", "0.5"],
    ]
    got = score_report(rows, {"a:W1": _at(3)}, _at(9), 1.0)
    assert list(got) == ["+3d"]
    assert abs(got["+3d"]["brier"] - 0.25) < TOLERANCE
