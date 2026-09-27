"""ARCHITECTURE.md is a paperkit projection whose claims assert against src/nemik; this keeps a
code change that falsifies one of them from passing the suite while the document goes stale."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("paperkit")

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_projection_gates_clean() -> None:
    r = subprocess.run([sys.executable, "-m", "paperkit.gate", str(ROOT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
