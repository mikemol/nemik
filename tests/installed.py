# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
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


def bin_env() -> tuple[Path, dict[str, str]]:
    """Give the directory of the installed scripts and the environment that runs them.

    Returns:
        The bin directory (under Bazel, the venv's in the runfiles) and the child environment.

    """
    runfiles = os.environ.get("RUNFILES_DIR") or os.environ.get("TEST_SRCDIR")
    if runfiles:
        venv = Path(runfiles) / "_main" / ".venv"
        home = (venv / "pythonhome.runfiles").read_text().strip()
        return venv / "bin", {**os.environ, "PYTHONHOME": str(Path(runfiles) / home)}
    return Path(sys.executable).parent, dict(os.environ)


def script(name: str) -> list[str]:
    """Give the argv of an installed script.

    Returns:
        The script's path, as a one-item argv list.

    Raises:
        FileNotFoundError: When the script is not installed.

    """
    path = bin_env()[0] / name
    if not path.exists():
        message = f"{name} is not installed in {path.parent}"
        raise FileNotFoundError(message)
    return [str(path)]


def run(
    name: str, *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run an installed script to completion, capturing its output as text.

    Returns:
        The finished process; a nonzero exit is left to the caller.

    """
    return subprocess.run(
        [*script(name), *args],
        env=bin_env()[1],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


def popen(
    name: str, *args: str, stdout: int | None = None, stderr: int | None = None
) -> subprocess.Popen[bytes]:
    """Start an installed script without waiting for it.

    Returns:
        The running process.

    """
    return subprocess.Popen(
        [*script(name), *args], env=bin_env()[1], stdout=stdout, stderr=stderr
    )


def announced(name: str, *args: str) -> list[str]:
    """nemik:W1060: run a script, read the first line it writes to stdout, stop it.

    Returns:
        The line's words; an empty list when it wrote none (it exited first).

    """
    proc: subprocess.Popen[bytes] = popen(
        name, *args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    told = proc.stdout.readline().decode().split() if proc.stdout else []
    proc.terminate()
    proc.wait()
    return told
