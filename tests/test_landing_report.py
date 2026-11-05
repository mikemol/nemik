# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1667: tools/landing_report.py prints UTC landing stamps, gaps and the gate."""

from datetime import UTC, datetime

from landing_report import gate_lines, landing_lines, landing_rows, stamp

REFLOG = (
    "6bc4cf34 main@{1793899885}: mikemol-commit stack\n"
    "d3b6d3e8 main@{1793896759}: mikemol-commit stack\n"
    "not a reflog line\n"
)


def test_a_reflog_line_becomes_a_utc_instant_and_a_short_sha() -> None:
    """The epoch inside `@{...}` is read as UTC; a line of another shape is skipped."""
    rows = landing_rows(REFLOG)
    assert [sha for _, sha in rows] == ["6bc4cf34", "d3b6d3e8"]
    assert rows[0][0] == datetime.fromtimestamp(1793899885, UTC)


def test_each_landing_line_gives_the_wall_gap_to_the_one_before() -> None:
    """The newest line carries the seconds since the older one; the oldest carries none."""
    lines = landing_lines(landing_rows(REFLOG))
    assert lines[0].endswith(", 3126 s (wall) after the one before")
    assert "after the one before" not in lines[1]
    assert lines[1].startswith(
        f"landed {stamp(datetime.fromtimestamp(1793896759, UTC))} d3b6d3e8"
    )


def test_the_gate_lines_give_the_state_and_begin_stamp_or_say_empty() -> None:
    """A stack prints its state, begin instant and cards; no stack or bad text prints empty."""
    held = '[{"state": "inflight", "waypoints": ["W1"], "began_ns": 1000000000}]'
    assert gate_lines(held) == ["gate: inflight began 1970-01-01T00:00:01Z ['W1']"]
    assert gate_lines("[]") == ["gate: empty"]
    assert gate_lines("not json") == ["gate: empty"]
