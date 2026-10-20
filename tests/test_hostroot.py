# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W773: the host-root frontier keeps the newest row of each id and flags a stale one."""

from nemik.hostroot import HostRow, latest, stale


def _row(ident: str, as_of: str, state: str = "done") -> HostRow:
    """Build a row with only the fields these tests vary.

    Returns:
        The row.

    """
    return HostRow(ident, state, as_of)


def test_latest_keeps_the_newest_row_of_each_id() -> None:
    """An id seen twice is its later as_of, whatever order the lines came in."""
    rows = [
        _row("a", "2026-10-20T10:00:00Z", "blocked"),
        _row("b", "2026-10-20T10:00:00Z"),
        _row("a", "2026-10-20T11:00:00Z", "done"),
        _row("b", "2026-10-20T09:00:00Z", "blocked"),
    ]
    kept = {row.ident: row.state for row in latest(rows)}
    assert kept == {"a": "done", "b": "done"}


def test_latest_orders_by_first_appearance_and_a_tie_goes_to_the_later_line() -> None:
    """Order is by first appearance; equal as_of takes the line read last."""
    rows = [
        _row("z", "2026-10-20T10:00:00Z", "blocked"),
        _row("a", "2026-10-20T10:00:00Z"),
        _row("z", "2026-10-20T10:00:00Z", "ready"),
    ]
    kept = latest(rows)
    assert [row.ident for row in kept] == ["z", "a"]
    assert kept[0].state == "ready"


def test_a_row_older_than_two_hours_is_stale() -> None:
    """Fresh within the window, stale past it, and stale when the stamp cannot be read."""
    now = "2026-10-20T14:00:00Z"
    assert not stale(_row("a", "2026-10-20T12:30:00Z"), now)
    assert stale(_row("a", "2026-10-20T11:30:00Z"), now)
    assert stale(_row("a", "not a stamp"), now)
