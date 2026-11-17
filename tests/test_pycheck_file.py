# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2055: one file's lint and type verdict is a bazel target that cannot pass silently."""

from pathlib import Path

HERE = Path(__file__).parent.parent
SCRIPT = HERE / "tools" / "pycheck_file.sh"


def test_the_target_is_declared_over_the_script_and_the_venv() -> None:
    """The BUILD file names //:pycheck_file, its script, the built venv and the lint config."""
    build = (HERE / "BUILD.bazel").read_text(encoding="utf-8")
    block = build[build.index('name = "pycheck_file"') :]
    assert 'srcs = ["tools/pycheck_file.sh"]' in block
    assert '":.venv"' in block
    assert "ruff-house.toml" in block
    assert "mypy-house.ini" in block


def test_the_script_runs_the_console_script_on_each_path() -> None:
    """It calls mikemol-pycheck --check-file per path and returns a refusal's status."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"$venv/bin/mikemol-pycheck" --check-file "$path"' in text
    assert "status=$?" in text
    assert 'exit "$status"' in text


def test_the_script_never_runs_the_module_form_that_passes_silently() -> None:
    """The module form has no __main__ guard, so it exits 0 on any file and must not be used."""
    commands = [
        line
        for line in SCRIPT.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    assert not any("-m mikemol.hooks.pycheck_cli" in line for line in commands)


def test_the_script_is_executable() -> None:
    """A bazel run executes the script directly, so it carries an execute bit."""
    assert SCRIPT.stat().st_mode & 0o111
