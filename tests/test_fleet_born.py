# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1112: a queue created inside the window is born, not work added to a plan."""

from datetime import UTC, datetime

from nemik.history import ROW_LINES, Counts, QueueDoc, born_cards, fleet_row

DOC: QueueDoc = {
    "waypoints": [{"symbol": "W1"}, {"symbol": "W2"}],
    "residue": [],
}
CARDS = 2
SINCE = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
INSIDE = "2026-10-26T23:48:00-04:00"
BEFORE = "2026-10-20T00:00:00+00:00"


def test_a_queue_whose_oldest_add_is_in_the_window_is_born() -> None:
    """Its cards are counted as born; an add before the window counts none."""
    assert born_cards(INSIDE, SINCE, DOC) == CARDS
    assert born_cards(BEFORE, SINCE, DOC) == 0


def test_the_oldest_add_decides_not_the_newest() -> None:
    """Adds come newest first; a queue re-added in the window was born earlier."""
    assert born_cards(f"{INSIDE}\n{BEFORE}", SINCE, DOC) == 0
    assert born_cards("", SINCE, DOC) == 0


def test_born_cards_stay_out_of_the_fleet_totals() -> None:
    """The totals count only the plans that existed; the new queue gets its own line."""
    rows: dict[str, Counts] = {"a": (2, 1, 0, 5)}
    lines = fleet_row(rows, "-1d", births={"e": 52})
    assert lines[0].startswith("fleet since -1d: closed 2, dropped 1, added 0, net +3")
    assert "52 cards born" in lines[0]
    assert lines[-1] == "e: born, 52 cards"


def test_the_birth_lines_count_against_the_line_cap() -> None:
    """Many new queues fold into the tail like any other changed repo."""
    births = {f"n{n:02d}": 1 for n in range(30)}
    lines = fleet_row({}, "-1d", births=births)
    assert len(lines) == ROW_LINES
    assert lines[-1] == "+22 more repos changed"
