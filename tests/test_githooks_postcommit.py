# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W819: a commit that adds or removes a module rebuilds the venv the fleet check runs from.

The Bazel-built .venv symlinks each src/nemik file, so an edit is seen at once but a new file is not
there until it is rebuilt. nemik:W818 added nemik/core and the stale venv made nemik-check crash on
import, which luthen's nemik_check gate read as unexpected_red (2026-10-20).
"""

from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".githooks" / "post-commit"


def _code() -> list[str]:
    """Read the hook's lines without comments.

    Returns:
        The non-comment, non-blank lines, stripped.

    """
    lines = [line.strip() for line in HOOK.read_text().splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def test_a_file_added_removed_or_renamed_under_src_nemik_triggers_the_rebuild() -> None:
    """The condition is the commit's own added, deleted or renamed files under src/nemik."""
    code = "\n".join(_code())
    assert "diff-tree" in code
    assert "--diff-filter=ADR" in code
    assert "HEAD -- src/nemik" in code
    assert "bazel build //:.venv" in code


def test_the_rebuild_is_detached_and_does_not_hold_the_commit() -> None:
    """The commit returns at once: the build runs in its own session in the background."""
    build = next(line for line in _code() if "bazel build //:.venv" in line)
    assert build.startswith("setsid nohup")
    assert build.endswith("&")


def test_the_rebuild_comes_before_the_push_exits_for_want_of_an_upstream() -> None:
    """A commit with nowhere to push still rebuilds: the step precedes the upstream check."""
    code = "\n".join(_code())
    assert code.index("bazel build //:.venv") < code.index("@{upstream}")
