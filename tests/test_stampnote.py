# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1568: tools/stampnote.py writes its own clock reading onto a card's evidence."""

from datetime import UTC, datetime, timedelta, timezone

from stampnote import command, main, stamp_text

WHEN = datetime(2026, 11, 4, 3, 33, 10, tzinfo=UTC)
USAGE = 2


def test_the_stamp_is_the_utc_clock_reading_between_the_label_and_the_text() -> None:
    """The note reads `<label> <time>Z: <text>`, whatever zone the clock was in."""
    assert stamp_text(WHEN, "G0", "gate empty") == "G0 2026-11-04T03:33:10Z: gate empty"
    local = WHEN.astimezone(timezone(timedelta(hours=-5)))
    assert stamp_text(local, "G0", "x") == "G0 2026-11-04T03:33:10Z: x"


def test_the_command_goes_through_the_writers_update_and_append() -> None:
    """The argv is the writer, its state, the card and the appended note, and nothing else."""
    assert command("pf", "/q.json", "W9", "G0 t: n") == [
        "pf",
        "--state",
        "/q.json",
        "--update",
        "W9",
        "--evidence-append",
        "G0 t: n",
    ]


def test_a_wrong_number_of_arguments_is_refused_before_anything_runs() -> None:
    """Two arguments are a usage error with status 2."""
    assert main(["W9", "G0"]) == USAGE
