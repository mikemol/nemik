# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1568: tools/stampnote.py writes its own clock reading onto a card's evidence."""

from datetime import UTC, datetime, timedelta, timezone

from stampnote import (
    command,
    flags,
    late_paths,
    main,
    manifest_of,
    pace_age_minutes,
    pace_lanes,
    stamp_text,
)

WHEN = datetime(2026, 11, 4, 3, 33, 10, tzinfo=UTC)
USAGE = 2
FRESH_AGE = 5
STALE_AGE = 33


def test_the_stamp_is_the_utc_clock_reading_between_the_label_and_the_text() -> None:
    """The note reads `<label> <time>Z: <text>`, whatever zone the clock was in."""
    assert stamp_text(WHEN, "G0", "gate empty") == "G0 2026-11-04T03:33:10Z: gate empty"
    local = WHEN.astimezone(timezone(timedelta(hours=-5)))
    assert stamp_text(local, "G0", "x") == "G0 2026-11-04T03:33:10Z: x"


def test_the_marks_come_before_the_text_and_only_when_there_are_any() -> None:
    """A fired check is visible at the head of the note."""
    assert stamp_text(WHEN, "G0", "x", "[LATE]") == "G0 2026-11-04T03:33:10Z: [LATE] x"
    assert stamp_text(WHEN, "G0", "x", "") == "G0 2026-11-04T03:33:10Z: x"


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


def test_the_pace_age_is_whole_minutes_from_the_quoted_stamp() -> None:
    """A note quoting `pace read stamp <time>` is aged at the stamp; one without is not."""
    fresh = "pace read stamp 2026-11-04T03:28:10Z: ruff 48"
    stale = "pace read of 2026-11-04T03:00:10Z, ruff 48"
    assert pace_age_minutes(WHEN, fresh) == FRESH_AGE
    assert pace_age_minutes(WHEN, stale) == STALE_AGE
    assert pace_age_minutes(WHEN, "no read quoted") is None
    assert pace_age_minutes(WHEN, "Pace read stamp 2026-11-04T03:00:10Z") == STALE_AGE


def test_manifest_paths_already_in_the_status_are_late() -> None:
    """A path git lists as changed (modified, added or untracked) marks the stamp late."""
    porcelain = " M src/nemik/a.py\n?? tools/new.py\nA  b.md\n"
    manifest = ["src/nemik/a.py", "tools/new.py", "c.py"]
    assert late_paths(manifest, porcelain) == ["src/nemik/a.py", "tools/new.py"]
    assert late_paths(manifest, "") == []


def test_the_manifest_is_read_from_the_writers_json() -> None:
    """Torn text and a card without a manifest give no paths."""
    assert manifest_of('{"manifest": ["a.py", "b.py"]}') == ["a.py", "b.py"]
    assert manifest_of('{"symbol": "W1"}') == []
    assert manifest_of("not json") == []


def test_the_flags_name_a_stale_read_and_the_late_paths() -> None:
    """Both labels are bracketed and joined; a fresh read on an unedited card adds none."""
    stale = "pace read stamp 2026-11-04T03:00:10Z"
    both = flags(WHEN, stale, ["a.py"])
    assert both == (
        "[PACE-STALE 33 min] [LATE: 1 manifest path(s) already modified: a.py]"
    )
    assert not flags(WHEN, "pace read stamp 2026-11-04T03:30:10Z", [])


PACE = """\
nemik: WARNING running from an editable install
pace of 2026-11-04T11:56:14Z; newest landing of nemik 2026-11-04T11:09:46Z: current
behind mtools hooks/pyproject.toml: fell 7 (pace of 2026-11-04T11:56:14Z)
behind nemik mypy-baseline.json: fell 35, owes 38 (pace of 2026-11-04T11:56:14Z)
ok nemik ruff-baseline.json; 5 left, 3 landings to zero (pace of 2026-11-04T11:56:14Z)
"""


def test_the_pace_lanes_are_the_stamp_and_only_nemiks_ratchet_lines() -> None:
    """A BUILD START stamp embeds the lane statuses, not another repo's lines."""
    lanes = pace_lanes(PACE)
    assert lanes.startswith("pace read stamp 2026-11-04T11:56:14Z: behind nemik mypy")
    assert "ok nemik ruff-baseline.json; 5 left, 3 landings to zero" in lanes
    assert "mtools" not in lanes
    assert not pace_lanes("no pace here")


def test_a_g0_without_a_quoted_pace_stamp_is_marked_and_other_labels_are_not() -> None:
    """The absence of a pace read in a G0 is as visible as a stale one."""
    assert flags(WHEN, "no read quoted", [], "G0") == "[NO-PACE-STAMP]"
    assert not flags(WHEN, "pace read stamp 2026-11-04T03:30:10Z", [], "G0")
    assert not flags(WHEN, "no read quoted", [], "LANDED")
