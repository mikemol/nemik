# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W355: nemik_commits_24h counts the commits in the window, the deploy-frequency signal."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from nemik import history
from nemik.metrics import commit_lines


def _three(repo: Path, since: str) -> int | None:
    """Answer as a repo with three commits in the window.

    Args:
        repo: The repo's directory, unused.
        since: The window start, unused.

    Returns:
        Three.

    """
    del repo, since
    return 3


def _no_history(repo: Path, since: str) -> int | None:
    """Answer as a directory with no git history does.

    Args:
        repo: The repo's directory, unused.
        since: The window start, unused.

    Returns:
        None.

    """
    del repo, since
    return None


def _fleet(root: Path) -> None:
    """Lay out one repo with a queue file.

    Args:
        root: The fleet root.

    """
    queue = root / "alpha" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    queue.write_text("{}", encoding="utf-8")


def test_a_repo_with_history_gets_a_sample(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Three commits in the window read as 3 for that repo."""
    _fleet(tmp_path)
    monkeypatch.setattr(history, "commits_since", _three)
    lines = commit_lines(tmp_path, datetime(2026, 10, 17, tzinfo=UTC))
    assert 'nemik_commits_24h{repo="alpha"} 3' in lines


def test_a_repo_with_no_history_gets_no_sample_not_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An export layout has no git; a 0 there would claim a quiet day."""
    _fleet(tmp_path)
    monkeypatch.setattr(history, "commits_since", _no_history)
    lines = commit_lines(tmp_path, datetime(2026, 10, 17, tzinfo=UTC))
    assert lines == ["# TYPE nemik_commits_24h gauge"]
