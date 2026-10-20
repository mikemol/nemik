# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W522, W536, W794: the house ruff and mypy rules are a paydown-only ratchet over the tree.

mtools selects every ruff rule and mypy's strict flags; nemik carries thousands of findings under
them, so mikemol-pycheck --ratchet (mtools:W1485/W1794) holds each file's count per rule to
ruff-baseline.json and mypy-baseline.json, which can only fall. This is that stage for both tools,
and a check that the ruff baseline names no vanished file. It runs in Bazel's sandbox of symlinked
sources too, since mtools:W1795 (8c8abe7) relativises a file as the tool reported it.
"""

import json
from pathlib import Path

import pytest
from mikemol.hooks.pycheck_cli import main

HERE = Path(__file__).absolute().parents[1]
ROOT = Path(__file__).resolve().parents[1]


def test_no_finding_is_above_either_baseline(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new finding, or a count above its file's baseline, fails the gate (exit 0 is clean).

    The package is importable from src, as the image installs it and as gate_staged.sh runs the
    ratchet: without that mypy meets src/nemik/x.py by path and by import and refuses it.
    """
    monkeypatch.setenv("PYTHONPATH", str(HERE / "src"))
    code = main(["--ratchet", str(HERE)])
    seen = capsys.readouterr()
    assert code == 0, seen.out + seen.err


def test_the_baseline_names_only_files_that_exist() -> None:
    """A baseline entry for a deleted or renamed file would hide a rise under the old name."""
    base = json.loads((ROOT / "ruff-baseline.json").read_text())
    assert [name for name in base if not (ROOT / name).is_file()] == []
