# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W676: a repo whose last acknowledged loop prompt differs from the current one is named."""

import os
from pathlib import Path

from nemik.idle import prompt_lag

HOUR = 3600
NOW = 1_800_000_000.0


def _fleet(root: Path, prompt: str | None) -> None:
    """Lay out a prompt (aged 5 hours) and four repos in different states of acknowledgement.

    Args:
        root: The fleet root.
        prompt: The prompt's text, or None for no prompt at all.

    """
    if prompt is not None:
        file = root / ".claude" / "loop-prompt.md"
        file.parent.mkdir(parents=True)
        file.write_text(prompt, encoding="utf-8")
        os.utime(file, (NOW - 5 * HOUR, NOW - 5 * HOUR))
    for repo, seen in (("current", "new\n"), ("behind", "old\n"), ("silent", None)):
        (root / repo).mkdir()
        if seen is not None:
            record = root / repo / ".git" / "mtools" / "loop-prompt.seen"
            record.parent.mkdir(parents=True)
            record.write_text(seen, encoding="utf-8")
    (root / "worktree").mkdir()
    (root / "worktree" / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")


def test_only_a_repo_with_a_different_reading_is_named_with_the_prompts_age(
    tmp_path: Path,
) -> None:
    """Only behind is named: current read it, silent never recorded one, a worktree is elsewhere."""
    _fleet(tmp_path, "new\n")
    got = prompt_lag(tmp_path, ["current", "behind", "silent", "worktree"], NOW)
    assert list(got) == ["behind"]
    assert "changed 5 h ago" in got["behind"]
    assert got["behind"].endswith("then --prompt-ack")


def test_a_fleet_with_no_prompt_names_nothing(tmp_path: Path) -> None:
    """No canonical prompt, nothing to be behind."""
    _fleet(tmp_path, None)
    assert prompt_lag(tmp_path, ["current", "behind"], NOW) == {}
