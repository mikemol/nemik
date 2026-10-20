# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W748: shingle rows are scored per lead against when each card was done."""

from nemik.verify import score_shingle

DAY = "2026-10-%02dT00:00:00+00:00"
TOLERANCE = 1e-9


def _at(day: int) -> str:
    return DAY % day


def test_a_row_is_scored_against_whether_the_card_was_done_by_its_lead() -> None:
    """W1 done day 3, W2 never; both forecast on day 1 at +3d with chance 0.5."""
    rows = [
        [_at(1), "a:W1", "+3d", "0", "0.5"],
        [_at(1), "a:W2", "+3d", "0", "0.5"],
    ]
    got = score_shingle(rows, {"a:W1": _at(3)}, _at(9), 1.0)
    assert abs(got["+3d"] - 0.25) < TOLERANCE


def test_rows_that_cannot_be_judged_are_left_out() -> None:
    """A horizon still ahead, a lead finer than the grain, a card done before issue."""
    rows = [
        [_at(8), "a:W1", "+3d", "0", "0.5"],
        [_at(1), "a:W2", "+1d", "0", "0.5"],
        [_at(5), "a:W3", "+3d", "0", "0.5"],
    ]
    done = {"a:W3": _at(4)}
    assert score_shingle(rows, done, _at(9), 2.0) == {}
