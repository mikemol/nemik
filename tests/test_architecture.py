# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""ARCHITECTURE.md is a paperkit projection whose claims assert against src/nemik.

This keeps a code change that falsifies one of them from passing the suite while the document
goes stale.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from mikemol.procrun.proc import capture

pytest.importorskip("paperkit")

# nemik:W2144: the sandbox's own tree, not the checkout a symlink resolves to. Resolved, the root
# was the real worktree, whose untracked .venv symlink (made by the gate, absent in a scratch tree)
# the claims' interpreter needs, so the same bytes passed in the gate and failed everywhere else.
# Absolute, the root is the runfiles tree, which holds exactly the target's named inputs in
# BUILD.bazel.
ROOT = Path(__file__).absolute().parents[1]


def test_architecture_projection_gates_clean() -> None:
    """Architecture projection gates clean."""
    r = capture([sys.executable, "-m", "paperkit.gate", str(ROOT)])
    assert r.returncode == 0, r.stdout + r.stderr
