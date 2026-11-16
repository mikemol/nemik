# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1140: a test's stop is the CPU it spends, never wall time, and the stop names itself."""

import sys
from pathlib import Path

import cpuline
import pytest
from mikemol.procrun.proc import capture

SPIN = """
import cpuline

cpuline.bound_cpu(1)
try:
    while True:
        pass
except cpuline.CpuBudgetError as stopped:
    print("STOPPED", stopped)
"""
TWICE = """
import cpuline

cpuline.bound_cpu(5)
cpuline.bound_cpu(500)
print("BUDGET", cpuline.CPU_SET)
"""


def run(script: Path, source: str) -> tuple[int, str, str]:
    """Run `source` in a fresh interpreter that can import cpuline.

    Returns:
        Its exit status, stdout and stderr.

    """
    script.write_text(source, encoding="utf-8")
    here = str(Path(cpuline.__file__).parent)
    done = capture([sys.executable, str(script)], env={"PYTHONPATH": here})
    return done.returncode, done.stdout, done.stderr


def test_a_spinning_process_fails_naming_its_cpu_budget(tmp_path: Path) -> None:
    """One CPU second of spinning raises CpuBudgetError, whatever the wall clock did."""
    code, out, err = run(tmp_path / "spin.py", SPIN)
    assert code == 0, err
    assert "STOPPED the test spent its CPU budget (1 CPU seconds)" in out


def test_the_first_budget_stands(tmp_path: Path) -> None:
    """A limit can only fall once set, so a second call neither raises it nor errors."""
    code, out, err = run(tmp_path / "twice.py", TWICE)
    assert code == 0, err
    assert "BUDGET [5]" in out


def test_the_handler_names_the_budget_it_was_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SIGXCPU's handler raises the named error and reads the budget that was set."""
    monkeypatch.setattr(cpuline, "CPU_SET", [7])
    with pytest.raises(cpuline.CpuBudgetError, match="7 CPU seconds"):
        cpuline.over(24, None)


def test_a_size_gives_twice_its_wall_seconds_and_unknown_reads_as_medium() -> None:
    """The budget follows the target's size; a size bazel does not name is medium."""
    assert cpuline.budget_for("small") == 2 * 60
    assert cpuline.budget_for("medium") == 2 * 300
    assert cpuline.budget_for("large") == 2 * 900
    assert cpuline.budget_for("enormous") == 2 * 3600
    assert cpuline.budget_for("") == cpuline.budget_for("medium")
