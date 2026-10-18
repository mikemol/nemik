# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W623: the pre-commit hook runs from a snapshot of itself, so a mid-run edit is safe."""

from pathlib import Path

HOOK = Path(__file__).parents[1] / ".githooks" / "pre-commit"


def test_the_hook_snapshots_itself_and_unlinks_the_copy() -> None:
    """The text shows the re-exec from a temporary copy and the copy's removal."""
    text = HOOK.read_text(encoding="utf-8")
    assert 'cp "$0" "$snapshot"' in text
    assert 'exec sh "$snapshot"' in text
    assert 'rm -f "$NEMIK_HOOK_SNAPSHOT"' in text


def test_the_snapshot_is_taken_before_anything_else_runs() -> None:
    """The re-exec comes before the first git call, after the bazel check that needs no tool."""
    text = HOOK.read_text(encoding="utf-8")
    at = text.index('exec sh "$snapshot"')
    assert at < text.index("git rev-parse")
    assert text.index("command -v bazel") < at


def test_the_copy_is_not_snapshotted_again() -> None:
    """The variable the parent sets is what stops the copy from copying itself in a loop."""
    text = HOOK.read_text(encoding="utf-8")
    assert 'if [ -z "${NEMIK_HOOK_SNAPSHOT:-}" ]' in text
    assert "NEMIK_HOOK_SNAPSHOT=$snapshot exec sh" in text
