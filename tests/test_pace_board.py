# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1051: the pace board always says whether its file was readable; absence is no answer."""

from pathlib import Path

from nemik.pacepublish import readable_lines
from nemik.serve import pace_board

HEAD = '{"as_of": "2026-10-25T14:00:00Z", "window": "10"}\n'
ROW = (
    '{"repo": "a", "ratchet": "x.json", "state": "%s", '
    '"observed": "0", "required": "1"}\n'
)
READABLE = "nemik_ratchet_pace_readable"


def test_the_gauge_is_one_or_zero_with_its_type_line() -> None:
    """Both values are written the same way, so a reader tells them apart by value."""
    assert readable_lines(1) == [f"# TYPE {READABLE} gauge", f"{READABLE} 1"]
    assert readable_lines(0) == [f"# TYPE {READABLE} gauge", f"{READABLE} 0"]


def test_a_readable_file_exports_readable_one_and_its_rows(tmp_path: Path) -> None:
    """The ordinary case keeps its gauges and adds the readable one."""
    path = tmp_path / "ratchet-pace.json"
    path.write_text(HEAD + ROW % "behind", encoding="utf-8")
    board, lines = pace_board(path)
    assert board["host"] is True
    assert f"{READABLE} 1" in lines
    assert 'nemik_ratchet_behind{repo="a",ratchet="x.json"} 1' in lines


def test_a_file_the_reader_refuses_exports_readable_zero_not_nothing(
    tmp_path: Path,
) -> None:
    """A state the reader does not know used to publish no gauges and clear every alert."""
    path = tmp_path / "ratchet-pace.json"
    path.write_text(HEAD + ROW % "sideways", encoding="utf-8")
    board, lines = pace_board(path)
    assert board["host"] is False
    assert lines == readable_lines(0)


def test_a_missing_file_exports_readable_zero_not_nothing(tmp_path: Path) -> None:
    """No file at all is also a signal."""
    board, lines = pace_board(tmp_path / "ratchet-pace.json")
    assert board["host"] is False
    assert lines == readable_lines(0)
