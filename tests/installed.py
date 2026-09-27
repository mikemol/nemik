"""nemik:W97: run a console script from the installed .venv, as a user would.

Host: the scripts sit beside the interpreter running pytest (.venv/bin). Bazel: the test's runfiles
carry //:.venv, whose sandboxed bin/python3 is a hardlink, not a symlink, so it is told where its
stdlib lives with PYTHONHOME (mtools venv.bzl, pythonhome.runfiles).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _bin() -> tuple[Path, dict[str, str]]:
    runfiles = os.environ.get("RUNFILES_DIR") or os.environ.get("TEST_SRCDIR")
    if runfiles:
        venv = Path(runfiles) / "_main" / ".venv"
        home = (venv / "pythonhome.runfiles").read_text().strip()
        return venv / "bin", {**os.environ, "PYTHONHOME": str(Path(runfiles) / home)}
    return Path(sys.executable).parent, dict(os.environ)


def script(name: str) -> list[str]:
    path = _bin()[0] / name
    assert path.exists(), f"{name} is not installed in {path.parent}"
    return [str(path)]


def run(name: str, *args: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([*script(name), *args], env=_bin()[1], capture_output=True, text=True, **kw)


def popen(name: str, *args: str, **kw) -> subprocess.Popen:
    return subprocess.Popen([*script(name), *args], env=_bin()[1], **kw)
