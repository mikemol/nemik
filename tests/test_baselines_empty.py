# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2088: ruff-baseline.json and mypy-baseline.json are exactly empty.

That is the end state of the campaign (no waivers, ratchets only fall). While it holds, an entry
cannot be added to either baseline by editing the data to match a new finding: pycheck --ratchet
compares findings with the tree's own baseline file, so an empty file is the only thing that makes
that comparison a refusal of every new finding.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["ruff-baseline.json", "mypy-baseline.json"])
def test_the_baseline_holds_nothing(name: str) -> None:
    """The file parses to an empty object."""
    parsed: object = json.loads((ROOT / name).read_text(encoding="utf-8"))
    assert parsed == {}
