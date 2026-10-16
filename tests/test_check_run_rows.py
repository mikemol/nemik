# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W557: tools/check_run_rows.py counts the rows of a run log that pass the run-row schema."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_run_rows", ROOT / "tools" / "check_run_rows.py"
)
assert SPEC
assert SPEC.loader
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
GOOD = {
    "ts": "2026-10-16T00:09:04Z",
    "run_id": "d12246912a134f44994f0fcc89421962",
    "trigger": "systemd-unit",
    "exit": 3,
    "verdict": {"state": "deferred"},
}
OLD = {"exit": 0, "set": "main", "state": "applied", "verdict": "{}", "when": "x"}


def _log(tmp_path: Path, rows: list[object]) -> str:
    """Write the rows as a JSON-lines log.

    Returns:
        The log's path.

    """
    log = tmp_path / "runs.jsonl"
    log.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return str(log)


def test_every_row_passing_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A log of clean rows exits 0 and says so."""
    assert TOOL.main([_log(tmp_path, [GOOD, GOOD])]) == 0
    assert "2 pass, 0 fail" in capsys.readouterr().out


def test_old_rows_fail_grouped_by_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Old rows are counted under one reason, not listed one by one."""
    assert TOOL.main([_log(tmp_path, [OLD, OLD, GOOD])]) == 1
    out = capsys.readouterr().out
    assert "2 rows: 'ts' is a required property" in out
    assert "1 pass, 2 fail" in out


def test_last_checks_only_the_tail(tmp_path: Path) -> None:
    """--last 1 sees only the final row, so old rows before it do not fail the run."""
    assert TOOL.main([_log(tmp_path, [OLD, OLD, GOOD]), "--last", "1"]) == 0


def test_an_unreadable_log_exits_unreadable(tmp_path: Path) -> None:
    """A missing log is its own exit code, not a pass."""
    assert TOOL.main([str(tmp_path / "missing.jsonl")]) == TOOL.UNREADABLE
