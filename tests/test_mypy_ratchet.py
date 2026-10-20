# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W543, W536: the mypy baseline names no vanished file.

The ratchet itself is mikemol-pycheck --ratchet (mtools:W1485/W1794), run for both tools by
tests/test_ruff_ratchet.py; mypy-house.ini holds mtools' strict flag set and mypy-baseline.json each
file's count per error code, which can only fall.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_baseline_names_only_files_that_exist() -> None:
    """A baseline entry for a deleted or renamed file would hide a rise under the old name."""
    base = json.loads((ROOT / "mypy-baseline.json").read_text())
    assert [name for name in base if not (ROOT / name).is_file()] == []
