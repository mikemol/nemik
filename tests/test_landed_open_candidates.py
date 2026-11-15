# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1083: nemik_landed_open_candidates counts ready cards that lead a landed commit.

It lists candidates, never ghosts: a card worked in slices leads a commit per slice, so the gauge
counts and closes nothing, and a history that cannot be read prints no sample (never a zero).
"""

import json
from typing import TYPE_CHECKING

from mikemol.procrun.proc import capture

from nemik.adapter import queue_graph
from nemik.history import recent_subjects
from nemik.metrics import candidate_lines, label

if TYPE_CHECKING:
    from pathlib import Path

    from rdflib import Graph

LOG = [
    "W1: the first slice",
    "W1: the second slice",
    "W2: a card that is blocked, not ready",
    "no symbol here: W3 is named only in the body",
]


def _card(symbol: str, status: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "title": "t",
        "status": status,
        "blocked_on": [],
        "enables": [],
        "evidence": "",
    }


def _fleet(root: Path, *, git: bool) -> Graph:
    """Lay out one repo with three cards, W1 and W3 ready and W2 blocked.

    Args:
        root: The fleet root.
        git: Whether the repo has a .git directory.

    Returns:
        The repo's queue graph.

    """
    queue = root / "alpha" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    state = {
        "version": 1,
        "project_root": str(root / "alpha"),
        "counter": 3,
        "residue": [],
        "waypoints": [_card("W1", "ready"), _card("W2", "blocked"), _card("W3", "ready")],
    }
    queue.write_text(json.dumps(state), encoding="utf-8")
    if git:
        (root / "alpha" / ".git").mkdir()
    return queue_graph("alpha", queue)


def test_a_ready_card_leading_a_landed_commit_is_counted_once(tmp_path: Path) -> None:
    """W1 leads two commits and counts once; W2 is not ready; W3 leads none."""
    g = _fleet(tmp_path, git=True)
    lines = candidate_lines(tmp_path, g, lambda _top: LOG)
    assert lines == [
        "# TYPE nemik_landed_open_candidates gauge",
        f"nemik_landed_open_candidates{label(repo='alpha')} 1",
    ]


def test_a_history_that_cannot_be_read_prints_no_sample(tmp_path: Path) -> None:
    """MUTANT: a refused log read as zero would say 'no candidates' of a repo nobody could read."""
    g = _fleet(tmp_path, git=True)
    assert candidate_lines(tmp_path, g, lambda _top: None) == [
        "# TYPE nemik_landed_open_candidates gauge"
    ]


def test_a_repo_with_no_git_directory_prints_no_sample(tmp_path: Path) -> None:
    """No history to read, so no sample."""
    g = _fleet(tmp_path, git=False)
    assert candidate_lines(tmp_path, g, lambda _top: LOG) == [
        "# TYPE nemik_landed_open_candidates gauge"
    ]


def _git(repo: Path, *args: str) -> None:
    """Run git in `repo` as a fixed author and fail the test when it exits nonzero."""
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "PATH": "/usr/bin:/bin",
    }
    done = capture(["git", "-C", str(repo), *args], env=env)
    assert done.returncode == 0, done.stderr


def test_recent_subjects_reads_a_real_repo_newest_first(tmp_path: Path) -> None:
    """The reader the gauge uses gives the subjects of a real history, newest first."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "W1: one")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "W2: two")
    assert recent_subjects(repo) == ["W2: two", "W1: one"]


def test_recent_subjects_is_none_without_a_history(tmp_path: Path) -> None:
    """A plain directory is no history, so None and never an empty list."""
    assert recent_subjects(tmp_path) is None
