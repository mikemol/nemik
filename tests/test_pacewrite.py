# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W997: the pace file written from the series reads back through pacepublish."""

from nemik.pacepublish import read_pace
from nemik.pacewrite import pace_rows, pace_text, priors_of

STAMP = "2026-10-25T00:00:00Z"
FALLING = list(range(30, 0, -1))
FLAT = [8] * 12
PRIOR = 5


def test_a_falling_and_a_flat_ratchet_are_judged_ok_and_behind() -> None:
    """Thirty falling by one per landing is ok; eight that never moves is behind."""
    series = [("a", "x.json", FALLING), ("b", "y.txt", FLAT)]
    rows = pace_rows(series, 10, {})
    assert [(r[0], r[2]) for r in rows] == [("a", "ok"), ("b", "behind")]


def test_the_file_reads_back_as_the_rows_written() -> None:
    """Write then read: the same stamp, window and rows."""
    rows = pace_rows([("a", "x.json", FALLING), ("b", "y.txt", FLAT)], 10, {})
    assert read_pace(pace_text(rows, STAMP, 10)) == (STAMP, 10, rows)


def test_the_requirement_carried_forward_only_rises() -> None:
    """A prior of five outlasts a series whose own seed is lower."""
    rows = pace_rows([("b", "y.txt", FLAT)], 10, {"b\ny.txt": PRIOR})
    assert rows[0][4] == PRIOR
    assert priors_of(rows) == {"b\ny.txt": PRIOR}
