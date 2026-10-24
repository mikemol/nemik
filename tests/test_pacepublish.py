# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W990: the pace file is read into rows and written as the gauges a gate and luthen read."""

from datetime import UTC, datetime

import pytest

from nemik.pacepublish import (
    as_of_lines,
    behind_ratchets,
    epoch_seconds,
    metric_lines,
    read_pace,
)

PACE = (
    '{"as_of": "2026-10-24T19:00:00Z", "window": "10", "rows": [\n'
    '  {"repo": "nemik", "ratchet": "ruff-baseline.json", "state": "behind",'
    ' "observed": "0", "required": "3"},\n'
    '  {"repo": "mtools", "ratchet": "scripts/x.txt", "state": "ok",'
    ' "observed": "4", "required": "2"}\n'
    "]}\n"
)
ROWS = [
    ("nemik", "ruff-baseline.json", "behind", 0, 3),
    ("mtools", "scripts/x.txt", "ok", 4, 2),
]
LABELS = 'repo="nemik",ratchet="ruff-baseline.json"'
STAMPS = [
    "1970-01-01T00:00:00Z",
    "2000-02-29T23:59:59Z",
    "2026-01-01T00:00:00Z",
    "2026-10-24T19:00:00Z",
    "2100-03-01T12:30:45Z",
]


def test_only_the_behind_ratchets_of_a_repo_are_named() -> None:
    """The repo's behind rows by ratchet path; an ok row and another repo's are left out."""
    assert behind_ratchets(ROWS, "nemik") == ["ruff-baseline.json"]
    assert behind_ratchets(ROWS, "mtools") == []


def test_the_pace_file_is_read_into_rows() -> None:
    """The stamp, the window and each row come back as written."""
    assert read_pace(PACE) == ("2026-10-24T19:00:00Z", 10, ROWS)


def test_the_gauges_carry_the_state_as_the_value() -> None:
    """Behind is 1 and ok is 0, per repo and ratchet, beside the two falls."""
    lines = metric_lines(ROWS, STAMPS[3])
    assert f"nemik_ratchet_pace_as_of {epoch_seconds(STAMPS[3])}" in lines
    assert f"nemik_ratchet_behind{{{LABELS}}} 1" in lines
    assert 'nemik_ratchet_behind{repo="mtools",ratchet="scripts/x.txt"} 0' in lines
    assert f"nemik_ratchet_fall_required{{{LABELS}}} 3" in lines


def test_the_stamp_becomes_unix_seconds_as_the_standard_library_reads_it() -> None:
    """Integer arithmetic agrees with datetime on leap days, year starts and a far date."""
    for stamp in STAMPS:
        want = int(datetime.fromisoformat(stamp).replace(tzinfo=UTC).timestamp())
        assert epoch_seconds(stamp) == want
    assert as_of_lines(STAMPS[0])[1] == "nemik_ratchet_pace_as_of 0"


def test_a_file_without_a_stamp_or_with_a_wrong_state_is_refused() -> None:
    """No as_of, a state beyond behind and ok, and a stamp that is no time are each refused."""
    with pytest.raises(ValueError, match="no as_of"):
        read_pace('{"rows": [\n]}\n')
    bad = PACE.replace('"state": "ok"', '"state": "fine"')
    with pytest.raises(ValueError, match="neither behind nor ok"):
        read_pace(bad)
    with pytest.raises(ValueError, match="not a UTC stamp"):
        read_pace(PACE.replace("2026-10-24T19:00:00Z", "yesterday"))
