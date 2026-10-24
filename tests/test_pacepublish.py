# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W990: the pace file is read into rows and written as the gauges a gate and luthen read."""

import pytest

from nemik.pacepublish import behind_ratchets, metric_lines, read_pace

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


def test_only_the_behind_ratchets_of_a_repo_are_named() -> None:
    """The repo's behind rows by ratchet path; an ok row and another repo's are left out."""
    assert behind_ratchets(ROWS, "nemik") == ["ruff-baseline.json"]
    assert behind_ratchets(ROWS, "mtools") == []


def test_the_pace_file_is_read_into_rows() -> None:
    """The stamp, the window and each row come back as written."""
    assert read_pace(PACE) == ("2026-10-24T19:00:00Z", 10, ROWS)


def test_the_gauges_carry_the_state_as_the_value() -> None:
    """Behind is 1 and ok is 0, per repo and ratchet, beside the two falls."""
    lines = metric_lines(ROWS)
    assert f"nemik_ratchet_behind{{{LABELS}}} 1" in lines
    assert 'nemik_ratchet_behind{repo="mtools",ratchet="scripts/x.txt"} 0' in lines
    assert f"nemik_ratchet_fall_required{{{LABELS}}} 3" in lines


def test_a_file_without_a_stamp_or_with_a_wrong_state_is_refused() -> None:
    """No as_of: refused. A state that is neither behind nor ok: refused."""
    with pytest.raises(ValueError, match="no as_of"):
        read_pace('{"rows": [\n]}\n')
    bad = PACE.replace('"state": "ok"', '"state": "fine"')
    with pytest.raises(ValueError, match="neither behind nor ok"):
        read_pace(bad)
