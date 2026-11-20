# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W866, W2382: the commit gate solves the Containerfile, and never skips the solve."""

import shutil
from pathlib import Path

from mikemol.procrun.proc import capture

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "image_solve.sh"
GATE = ROOT / "tools" / "gate_staged.sh"
CONTAINERFILE = ROOT / "Containerfile"
CANNOT_RUN = 7
FAILED = 1


def _stages() -> list[str]:
    """Name the Containerfile's stages.

    Returns:
        Each `FROM ... AS <name>`'s name, in order.

    """
    return [
        line.rsplit(" AS ", 1)[1].strip()
        for line in CONTAINERFILE.read_text(encoding="utf-8").splitlines()
        if line.startswith("FROM ") and " AS " in line
    ]


def _run(tmp_path: Path, buildctl: str | None) -> tuple[int, str]:
    """Run the script with only a stub buildctl (or none) on PATH.

    Returns:
        The exit status and what the script printed.

    """
    stubs = tmp_path / "bin"
    stubs.mkdir()
    if buildctl is not None:
        stub = stubs / "buildctl"
        stub.write_text(f"#!/bin/sh\n{buildctl}\n", encoding="utf-8")
        stub.chmod(0o755)
    bash = shutil.which("bash")
    assert bash is not None
    done = capture([bash, str(SCRIPT), str(tmp_path)], env={"PATH": str(stubs)})
    return done.returncode, done.stdout


def test_the_solve_builds_the_gated_path_the_containerfile_defines() -> None:
    """The file and TESTS value it passes exist: a stage by that name, a global ARG for it."""
    script = SCRIPT.read_text(encoding="utf-8")
    filename = script.split("--opt filename=", 1)[1].split()[0]
    value = script.split("--opt build-arg:TESTS=", 1)[1].split()[0]
    text = CONTAINERFILE.read_text(encoding="utf-8")
    assert filename == CONTAINERFILE.name
    assert value in _stages()
    assert text.index("ARG TESTS=") < text.index("FROM ")


def test_no_buildctl_cannot_run_and_says_so(tmp_path: Path) -> None:
    """The check cannot run without buildctl: exit 7, never a skip that passes."""
    status, out = _run(tmp_path, None)
    assert status == CANNOT_RUN
    assert "no buildctl" in out


def test_no_buildkit_daemon_cannot_run_and_says_so(tmp_path: Path) -> None:
    """A buildctl that no daemon answers is the same: exit 7 naming the daemon."""
    status, out = _run(tmp_path, 'if [ "$1" = debug ]; then exit 1; fi; exit 0')
    assert status == CANNOT_RUN
    assert "no BuildKit daemon" in out


def test_a_failed_solve_is_exit_one_not_buildctls_own_status(tmp_path: Path) -> None:
    """A failed solve is 1, so it cannot be mistaken for the 7 of a check that did not run."""
    status, _ = _run(tmp_path, 'if [ "$1" = debug ]; then exit 0; fi; exit 7')
    assert status == FAILED


def test_a_solve_that_holds_is_exit_zero(tmp_path: Path) -> None:
    """The control: a daemon that answers and a build that succeeds."""
    assert _run(tmp_path, "exit 0")[0] == 0


def test_the_gate_solves_when_the_containerfile_or_the_workflow_changes() -> None:
    """The step diffs HEAD against the staged tree, runs the script and refuses on any status."""
    gate = GATE.read_text(encoding="utf-8")
    assert "Containerfile | .forgejo/workflows/build.yml) solve_needed=1" in gate
    assert 'git -C "$real_root" diff --name-only "$head_sha" "$tree"' in gate
    assert 'sh tools/image_solve.sh "$wt"' in gate
    assert 'exit "$solve_status"' in gate
    assert "was not solved here" not in gate
    assert gate.index("tools/image_solve.sh") < gate.index("bazel test //:precommit")
