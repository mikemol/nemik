# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W522: the house ruff rules are a paydown-only ratchet over the whole tree.

mtools selects every ruff rule; nemik carries thousands of findings under them, so
tools/ruff_ratchet.py holds each file's count per rule to a baseline that can only fall (see its
docstring). This is that stage in the gate, and a check that its baseline names no vanished file.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "ruff_ratchet.py"


def _tool() -> subprocess.CompletedProcess[str]:
    """Run the ratchet's check over this tree.

    Returns:
        The finished process, whose exit status is the ratchet's verdict.

    """
    return subprocess.run(
        [sys.executable, str(TOOL)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )


def test_no_finding_is_above_the_baseline() -> None:
    """A new finding, or a count above its file's baseline, fails the gate."""
    run = _tool()
    assert run.returncode == 0, run.stderr


def test_the_baseline_names_only_files_that_exist() -> None:
    """A baseline entry for a deleted or renamed file would hide a rise under the old name."""
    base = json.loads((ROOT / "ruff-baseline.json").read_text())
    assert [name for name in base if not (ROOT / name).is_file()] == []
