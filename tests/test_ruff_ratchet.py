# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W522, W536: the house ruff and mypy rules are a paydown-only ratchet over the whole tree.

mtools selects every ruff rule and mypy's strict flags; nemik carries thousands of findings under
them, so mikemol-pycheck --ratchet (mtools:W1485/W1794) holds each file's count per rule to
ruff-baseline.json and mypy-baseline.json, which can only fall. This is that stage for both tools,
and a check that the ruff baseline names no vanished file.

Inside Bazel's sandbox every source is a symlink out to the checkout, and the shared ratchet
resolves each reported file and takes it relative to the root, which fails (ValueError, mtools
pyratchet._pair). There the ratchet test skips and says why; tools/gate_staged.sh runs the same
command on the staged worktree, whose files are real, before the suite.
"""

import json
from pathlib import Path

import pytest
from mikemol.hooks.pycheck_cli import main

HERE = Path(__file__).absolute().parents[1]
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    (HERE / "src" / "nemik" / "__init__.py").is_symlink(),
    reason="a symlinked sandbox: the shared ratchet resolves files out of the root; "
    "gate_staged.sh runs it on the real staged tree",
)
def test_no_finding_is_above_either_baseline(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new finding, or a count above its file's baseline, fails the gate (exit 0 is clean).

    The package is importable from src, as the image installs it and as gate_staged.sh runs the
    ratchet: without that mypy meets src/nemik/x.py by path and by import and refuses it.
    """
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "src"))
    code = main(["--ratchet", str(ROOT)])
    seen = capsys.readouterr()
    assert code == 0, seen.out + seen.err


def test_the_baseline_names_only_files_that_exist() -> None:
    """A baseline entry for a deleted or renamed file would hide a rise under the old name."""
    base = json.loads((ROOT / "ruff-baseline.json").read_text())
    assert [name for name in base if not (ROOT / name).is_file()] == []
