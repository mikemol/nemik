# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2125: the CPython shim finds the mikemol tools where nemik-work always looked.

nemik.work compiles under the pinned Codon, which has no sys.executable and no tempfile, so it
takes an Env (github-14's ruling: not argv[0], which changes under -m and pytest, and not a PATH
lookup, which could find a tool that is not the pinned one). nemik.shims.work_cli builds it from
the directory of the running interpreter, the venv's bin where the console scripts and the
mikemol tools live, and the system temp directory, and the callers (nemik-ask, nemik-witnesses,
nemik-check, the stalled report) go through it. nemik.shims is outside the Codon census, which
reads only the top-level modules and nemik.core.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from nemik import work
from nemik.shims import work_cli

FAKE_STATUS = 7


def test_the_env_is_the_interpreters_directory_and_the_system_temp_root() -> None:
    """Build the Env from the directory beside sys.executable and tempfile.gettempdir()."""
    made = work_cli.env()
    assert made.tool_dir == str(Path(sys.executable).parent)
    assert made.temp_root == tempfile.gettempdir()


def test_the_cli_passes_its_own_arguments_and_its_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return what main returns, called over sys.argv[1:] and this process's Env."""
    seen: list[object] = []

    def fake_main(argv: list[str], env: work.Env) -> int:
        seen.extend([argv, env.tool_dir, env.temp_root])
        return FAKE_STATUS

    monkeypatch.setattr(work, "main", fake_main)
    monkeypatch.setattr(sys, "argv", ["nemik-work", "W1", "--dry-run"])
    assert work_cli.cli() == FAKE_STATUS
    made = work_cli.env()
    assert seen == [["W1", "--dry-run"], made.tool_dir, made.temp_root]


def test_the_callers_views_fill_in_the_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Hand this process's Env to the compiled module from run_writer and in_gate."""
    got: list[object] = []

    def fake_writer(argv: list[str], env: work.Env) -> tuple[int, str]:
        got.append((argv, env.tool_dir))
        return 0, "ok"

    def fake_gate(repo_dir: Path, env: work.Env) -> set[str]:
        got.append((repo_dir, env.tool_dir))
        return {"W1"}

    monkeypatch.setattr(work, "run_writer", fake_writer)
    monkeypatch.setattr(work, "in_gate", fake_gate)
    assert work_cli.run_writer(["--check"]) == (0, "ok")
    assert work_cli.in_gate(tmp_path) == {"W1"}
    tool_dir = work_cli.env().tool_dir
    assert got == [(["--check"], tool_dir), (tmp_path, tool_dir)]


def test_the_coreutils_timeout_command_is_present() -> None:
    """Find `timeout`, which nemik.spawn runs as `timeout N prog`, where nemik-work runs."""
    assert shutil.which("timeout") is not None
