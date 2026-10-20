# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W759: a stored shingle is scored against the events at the commit-grain floor."""

from nemik.history import first_done, score_rows, shingle_lines

SHA = "abc123"
DAY = "2026-10-%02dT00:00:00+00:00"
TOLERANCE = 1e-9


def _at(day: int) -> str:
    return DAY % day


def test_the_first_done_of_each_card_is_its_first_status_to_done() -> None:
    """A reopen and a second done do not move it."""
    events = [
        ("a:W1", _at(3), "status", "ready", "done", SHA),
        ("a:W1", _at(5), "status", "done", "ready", SHA),
        ("a:W1", _at(7), "status", "ready", "done", SHA),
        ("a:W2", _at(4), "status", "", "ready", SHA),
    ]
    assert first_done(events) == {"a:W1": _at(3)}


def test_stored_rows_are_scored_per_lead_down_to_the_commit_grain() -> None:
    """W1 done day 3; forecast day 1: +3d at 0.5 is scored, +0.5d is finer than a day."""
    events = [("a:W1", _at(3), "status", "ready", "done", SHA)]
    rows = [
        [_at(1), "a:W1", "+3d", "0", "0.5"],
        [_at(1), "a:W1", "+0.5d", "0", "0.5"],
    ]
    got = score_rows(rows, events, _at(9))
    assert list(got) == ["+3d"]
    assert abs(got["+3d"] - 0.25) < TOLERANCE


def test_lines_that_are_not_rows_are_skipped_when_a_shingle_is_read() -> None:
    """A blank line and a wrapper's status line do not crash the reader."""
    text = f"{_at(1)}\ta:W1\t+3d\t0\t0.5\n\n[exited with code 0]\n"
    assert shingle_lines(text) == [[_at(1), "a:W1", "+3d", "0", "0.5"]]
