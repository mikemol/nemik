# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W589: the image replica script runs the stage the Containerfile defines, no other."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "image_replica.sh"
CONTAINERFILE = ROOT / "Containerfile"


def test_the_script_builds_the_containerfiles_test_stage() -> None:
    """The target and file names it passes to buildctl exist in the Containerfile."""
    script = SCRIPT.read_text(encoding="utf-8")
    target = script.split("--opt target=", 1)[1].split()[0]
    filename = script.split("--opt filename=", 1)[1].split()[0]
    assert filename == CONTAINERFILE.name
    stages = [
        line.rsplit(" AS ", 1)[1].strip()
        for line in CONTAINERFILE.read_text(encoding="utf-8").splitlines()
        if line.startswith("FROM ") and " AS " in line
    ]
    assert target in stages


def test_the_script_is_executable_with_a_bash_shebang() -> None:
    """The executable bit and the shebang are set so a hook can run it."""
    assert os.access(SCRIPT, os.X_OK)
    assert SCRIPT.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash\n")


def test_the_scratch_clone_is_removed_on_every_exit() -> None:
    """The EXIT trap stays, and buildctl is not exec'd, since exec would skip the trap."""
    script = SCRIPT.read_text(encoding="utf-8")
    assert "trap 'rm -rf \"$scratch\"' EXIT" in script
    assert "exec buildctl" not in script


def test_post_commit_starts_the_runner_detached_after_the_push() -> None:
    """The runner starts after the push, detached with setsid and in the background."""
    hook = (ROOT / ".githooks" / "post-commit").read_text(encoding="utf-8")
    push = hook.index("git push")
    start = hook.index("tools/image_replica_runner.sh >/dev/null 2>&1 &")
    assert push < start
    assert "setsid nohup tools/image_replica_runner.sh" in hook
    assert hook.rstrip().endswith("exit 0")
