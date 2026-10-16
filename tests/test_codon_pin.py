# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W566: the staged Codon compiler is the pinned 0.20.3 and rejects what nemik must remove.

MODULE.bazel pins Codon as a hashed input (the operator aims all Python at Codon compatibility,
nemik:W561). This holds the pin to what it was measured to do: report 0.20.3, run a typed program,
and refuse `from __future__ import annotations`, the line that blocks most modules (nemik:W562).
"""

import os
from pathlib import Path

import installed
import pytest

_STAGED = os.environ.get("NEMIK_CODON")
if not _STAGED:
    pytest.skip(
        "the pinned Codon comes from bazel (MODULE.bazel @codon, W566)",
        allow_module_level=True,
    )
CODON = Path(_STAGED).resolve()
TYPED = "def add(a: int, b: int) -> int:\n    return a + b\n\nprint(add(2, 3))\n"


def test_the_staged_compiler_is_the_pinned_version() -> None:
    """The binary reports the version MODULE.bazel pins."""
    assert installed.run(str(CODON), "--version").stdout.strip() == "0.20.3"


def test_a_typed_program_runs(tmp_path: Path) -> None:
    """A small typed program compiles and prints its result."""
    program = tmp_path / "typed.py"
    program.write_text(TYPED)
    run = installed.run(str(CODON), "run", str(program))
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "5"


def test_the_future_import_is_rejected_by_name(tmp_path: Path) -> None:
    """Codon refuses the annotations future, and says which module it could not find."""
    program = tmp_path / "future.py"
    program.write_text("from __future__ import annotations\n\nprint(1)\n")
    run = installed.run(str(CODON), "run", str(program))
    assert run.returncode != 0
    assert "__future__" in run.stderr
