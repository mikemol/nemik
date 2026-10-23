# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W866: the commit gate solves the Containerfile when it or its workflow changes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "image_solve.sh"
GATE = ROOT / "tools" / "gate_staged.sh"
CONTAINERFILE = ROOT / "Containerfile"
SKIPPED = "exit 3"


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


def test_the_solve_builds_the_gated_path_the_containerfile_defines() -> None:
    """The file and TESTS value it passes exist: a stage by that name, a global ARG for it."""
    script = SCRIPT.read_text(encoding="utf-8")
    filename = script.split("--opt filename=", 1)[1].split()[0]
    value = script.split("--opt build-arg:TESTS=", 1)[1].split()[0]
    text = CONTAINERFILE.read_text(encoding="utf-8")
    assert filename == CONTAINERFILE.name
    assert value in _stages()
    assert text.index("ARG TESTS=") < text.index("FROM ")


def test_no_buildkit_is_a_skip_and_never_a_failure() -> None:
    """No buildctl and no daemon both exit 3, which the gate reports and goes on."""
    script = SCRIPT.read_text(encoding="utf-8")
    assert script.count(SKIPPED) == len(("no buildctl", "no daemon"))


def test_the_gate_solves_when_the_containerfile_or_the_workflow_changes() -> None:
    """The step diffs HEAD against the staged tree, runs the script and says why it skipped."""
    gate = GATE.read_text(encoding="utf-8")
    assert "Containerfile | .forgejo/workflows/build.yml) solve_needed=1" in gate
    assert 'git -C "$real_root" diff --name-only "$head_sha" "$tree"' in gate
    assert 'sh tools/image_solve.sh "$wt"' in gate
    assert "was not solved here" in gate
    assert "the image build would fail: commit refused" in gate
    assert gate.index("tools/image_solve.sh") < gate.index("bazel test //:precommit")
