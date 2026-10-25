# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1030: a pace run reads a store answer and the last file and writes the next one."""

from pathlib import Path

import pytest

from nemik.hostroot_cli import main
from nemik.pacepublish import read_pace
from nemik.pacerun import pace_document

REFUSES = pytest.raises(ValueError, match="no ratchet series")
EXPORT = Path(__file__).parent / "fixtures" / "ratchet" / "nemik_export.jsonl"
STAMP = "2026-10-25T05:00:00Z"
RAISED = 7
LAST_HEAD = '{"as_of": "2026-10-24T00:00:00Z", "window": "10"}\n'
LAST_ROW = (
    '{"repo": "a", "ratchet": "x.json", "state": "behind", '
    '"observed": "0", "required": "7"}\n'
)


def _answer(values: list[int]) -> str:
    """Write a range-query answer holding one series of the given values.

    Returns:
        The answer's JSON text, built as text so no untyped json call is referenced.

    """
    metric = '{"repo": "a", "ratchet": "x.json", "kind": "entries"}'
    samples = ", ".join(f'[{1000 + n}, "{v}"]' for n, v in enumerate(values))
    series = f'[{{"metric": {metric}, "values": [{samples}]}}]'
    data = f'{{"resultType": "matrix", "result": {series}}}'
    return f'{{"status": "success", "data": {data}}}'


def test_a_flat_series_is_behind_and_the_file_reads_back() -> None:
    """Eight that never moves owes the floor of one and has fallen none."""
    stamp, window, rows = read_pace(pace_document(_answer([8] * 12), "", STAMP))
    assert (stamp, window) == (STAMP, 10)
    assert rows == [("a", "x.json", "behind", 0, 1)]


def test_the_last_files_requirement_is_carried_forward() -> None:
    """A requirement of seven stated last time is not lowered by a series that seeds one."""
    rows = read_pace(pace_document(_answer([8] * 12), LAST_HEAD + LAST_ROW, STAMP))[2]
    assert rows[0][4] == RAISED


def test_an_unreadable_last_file_seeds_nothing() -> None:
    """Text that is no pace file is ignored, not fatal."""
    rows = read_pace(pace_document(_answer([8] * 12), "not a pace file", STAMP))[2]
    assert rows[0][4] == 1


def test_a_raw_export_is_judged_one_value_per_gate_run() -> None:
    """The recorded export of nemik's baselines: seven runs, shorter than the window, behind."""
    rows = read_pace(pace_document(EXPORT.read_text(encoding="utf-8"), "", STAMP))[2]
    assert [(row[1], row[2]) for row in rows] == [
        ("codon-baseline.json", "behind"),
        ("mypy-baseline.json", "behind"),
        ("ruff-baseline.json", "behind"),
    ]


def test_an_export_with_no_series_refuses_instead_of_writing_an_empty_file() -> None:
    """Nothing to judge raises, so the last good file is kept."""
    with REFUSES:
        pace_document("", "", STAMP)


def test_hostroot_writes_the_pace_file_from_a_stored_answer(tmp_path: Path) -> None:
    """--answer reads the stored answer and writes the file named by --out."""
    answer, out = tmp_path / "answer.json", tmp_path / "ratchet-pace.json"
    answer.write_text(_answer([8] * 12), encoding="utf-8")
    assert main(["--answer", str(answer), "--out", str(out)]) == 0
    rows = read_pace(out.read_text(encoding="utf-8"))[2]
    assert (rows[0][0], rows[0][1], rows[0][2]) == ("a", "x.json", "behind")


def test_hostroot_refuses_an_answer_that_is_not_a_matrix(tmp_path: Path) -> None:
    """A failed query leaves no file, and the command says it did not write."""
    answer, out = tmp_path / "answer.json", tmp_path / "ratchet-pace.json"
    answer.write_text('{"status": "error"}', encoding="utf-8")
    assert main(["--answer", str(answer), "--out", str(out)]) == 1
    assert not out.exists()
