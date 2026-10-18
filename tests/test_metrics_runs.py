# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W565: nemik-metrics reports how many source run-log lines predate the run-row shape."""

import json
from pathlib import Path

import pytest

from nemik.metrics import main, run_log_lines

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_no_directory_prints_nothing() -> None:
    """Without --runs there is no family and no TYPE line."""
    assert run_log_lines(None) == []


def test_the_index_counts_become_one_gauge_per_stream(tmp_path: Path) -> None:
    """index.json's unmigrated counts print by stream; a stream with no count is left out."""
    index = {
        "apply_set_runs": {"rows": 10, "unmigrated": 491},
        "apply_ledger": {"rows": 3, "unmigrated": 425},
        "reaper_runs": {"rows": 0},
    }
    (tmp_path / "index.json").write_text(json.dumps(index), encoding="utf-8")
    lines = run_log_lines(tmp_path)
    assert lines[0] == "# TYPE nemik_run_log_unmigrated gauge"
    assert lines[1:] == [
        'nemik_run_log_unmigrated{stream="apply_ledger"} 425',
        'nemik_run_log_unmigrated{stream="apply_set_runs"} 491',
    ]


def test_a_directory_without_an_index_prints_nothing(tmp_path: Path) -> None:
    """A missing index is silence, not a zero."""
    assert run_log_lines(tmp_path) == []


def test_the_family_is_in_the_run_with_runs_and_has_help(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A plain run with --runs prints the HELP line and the gauge."""
    index: dict[str, dict[str, int]] = {"apply_set_runs": {"rows": 1, "unmigrated": 7}}
    (tmp_path / "index.json").write_text(json.dumps(index), encoding="utf-8")
    main(
        [
            "--root",
            str(FLEET),
            "--spool",
            str(tmp_path / "none.jsonl"),
            "--runs",
            str(tmp_path),
        ]
    )
    out = capsys.readouterr().out
    assert "# HELP nemik_run_log_unmigrated" in out
    assert 'nemik_run_log_unmigrated{stream="apply_set_runs"} 7' in out
