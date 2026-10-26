# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W997: the pace file written from the series reads back through pacepublish."""

from nemik.pacepublish import read_extras, read_pace
from nemik.pacewrite import extras_of, pace_rows, pace_text, priors_of

STAMP = "2026-10-25T00:00:00Z"
FALLING = list(range(30, 0, -1))
FLAT = [8] * 12
PRIOR = 5


def test_a_falling_and_a_flat_ratchet_are_judged_ok_and_behind() -> None:
    """Thirty falling by one per landing is ok; eight that never moves is behind."""
    series = [("a", "x.json", FALLING), ("b", "y.txt", FLAT)]
    rows = pace_rows(series, 10, {}, [])
    assert [(r[0], r[2]) for r in rows] == [("a", "ok"), ("b", "behind")]


def test_the_file_reads_back_as_the_rows_written() -> None:
    """Write then read: the same stamp, window and rows."""
    rows = pace_rows([("a", "x.json", FALLING), ("b", "y.txt", FLAT)], 10, {}, [])
    assert read_pace(pace_text(rows, STAMP, 10, {})) == (STAMP, 10, rows)


def test_a_row_states_its_value_and_landings_to_zero_when_asked() -> None:
    """W1114: one left falling a landing is 1 landing off; a flat ratchet has no horizon."""
    series = [("a", "x.json", FALLING), ("b", "y.txt", FLAT)]
    rows = pace_rows(series, 10, {}, [])
    extras = extras_of(series, 10)
    assert extras == {"a\nx.json": (1, 1), "b\ny.txt": (8, -1)}
    text = pace_text(rows, STAMP, 10, extras)
    assert read_extras(text) == extras
    assert read_pace(text) == (STAMP, 10, rows)


def test_a_file_written_before_the_horizon_states_none() -> None:
    """A row without value and horizon reads as no extras, not as an error."""
    rows = pace_rows([("a", "x.json", FALLING)], 10, {}, [])
    assert read_extras(pace_text(rows, STAMP, 10, {})) == {}


def test_the_requirement_carried_forward_only_rises() -> None:
    """A prior of five outlasts a series whose own seed is lower."""
    rows = pace_rows([("b", "y.txt", FLAT)], 10, {"b\ny.txt": PRIOR}, [])
    assert rows[0][4] == PRIOR
    assert priors_of(rows) == {"b\ny.txt": PRIOR}


def test_an_ended_series_reads_unknown_with_the_requirement_it_last_stated() -> None:
    """The flat series would be behind, but it ended: unknown, observed 0, the prior kept."""
    rows = pace_rows([("b", "y.txt", FLAT)], 10, {"b\ny.txt": PRIOR}, [("b", "y.txt")])
    assert rows == [("b", "y.txt", "unknown", 0, PRIOR)]
