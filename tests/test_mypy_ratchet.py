# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W543: the house mypy flags are a paydown-only ratchet over the whole tree.

mypy-house.ini holds mtools' strict flag set and nemik carries thousands of findings under it, so
tools/mypy_ratchet.py holds each file's count per error code to a baseline that can only fall (see
its docstring). This is that stage in the gate, a check that its baseline names no vanished file,
and the ratchet's own comparison logic.
"""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "mypy_ratchet.py"
SPEC = importlib.util.spec_from_file_location("mypy_ratchet", TOOL)
assert SPEC
assert SPEC.loader
RATCHET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RATCHET)


def test_no_finding_is_above_the_baseline() -> None:
    """A new finding, or a count above its file's baseline, fails the gate."""
    assert RATCHET.main([]) == 0


def test_the_baseline_names_only_files_that_exist() -> None:
    """A baseline entry for a deleted or renamed file would hide a rise under the old name."""
    base = json.loads((ROOT / "mypy-baseline.json").read_text())
    assert [name for name in base if not (ROOT / name).is_file()] == []


def test_a_rise_in_a_count_is_a_regression() -> None:
    """A count above the baseline, or a code with no baseline entry, is named."""
    base = {"a.py": {"misc": 2}}
    now = {"a.py": {"misc": 3, "no-any-return": 1}, "b.py": {"misc": 1}}
    assert RATCHET.regressions(now, base) == [
        "a.py: misc 3 > baseline 2",
        "a.py: no-any-return 1 > baseline 0",
        "b.py: misc 1 > baseline 0",
    ]


def test_a_paydown_is_not_a_regression() -> None:
    """A count that falls, or a file that drops out, raises nothing."""
    base = {"a.py": {"misc": 2}, "b.py": {"misc": 1}}
    assert RATCHET.regressions({"a.py": {"misc": 1}}, base) == []
