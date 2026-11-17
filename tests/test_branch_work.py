# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2251: work on a branch that never reaches the trunk is visible, from git alone."""

from typing import TYPE_CHECKING

from mikemol.procrun.proc import capture

from nemik.history import branch_work, trunk_of
from nemik.metrics import branch_lines, label

if TYPE_CHECKING:
    from pathlib import Path

ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "PATH": "/usr/bin:/bin",
}
OLD = "2020-01-01T00:00:00+00:00"
TWO = 2


def _git(repo: Path, *args: str, when: str = "") -> None:
    """Run git in `repo` as a fixed author, at `when` if given, and fail the test on an error."""
    env = {**ENV, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when} if when else ENV
    done = capture(["git", "-C", str(repo), *args], env=env)
    assert done.returncode == 0, done.stderr


def _commit(repo: Path, name: str, when: str = "") -> None:
    """Add a file and commit it."""
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", name, when=when)


def _repo(path: Path, trunk: str = "main") -> Path:
    """Start a repository whose first branch is `trunk`, with one commit on it.

    Returns:
        The repository's directory.

    """
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", trunk)
    _commit(path, "base")
    return path


def test_a_branch_ahead_of_main_is_listed_with_its_commits(tmp_path: Path) -> None:
    """A feature branch two commits ahead shows ahead 2; main itself does not appear."""
    repo = _repo(tmp_path / "r")
    _git(repo, "checkout", "-q", "-b", "feature/x")
    _commit(repo, "one")
    _commit(repo, "two")
    rows = branch_work(repo)
    assert [(name, ahead) for name, ahead, _ in rows] == [("feature/x", TWO)]
    assert rows[0][2] > 0


def test_a_merged_branch_and_a_stale_one_are_left_out(tmp_path: Path) -> None:
    """Ahead 0 (merged) and a newest commit older than the window are not current work."""
    repo = _repo(tmp_path / "r")
    _git(repo, "branch", "merged")
    _git(repo, "checkout", "-q", "-b", "stale")
    _commit(repo, "old", when=OLD)
    _git(repo, "checkout", "-q", "main")
    assert branch_work(repo) == []


def test_the_trunk_is_origin_head_when_the_repo_has_one(tmp_path: Path) -> None:
    """A repo whose trunk is called trunk counts from it, and its own branch is not a branch."""
    repo = _repo(tmp_path / "r", trunk="trunk")
    _git(repo, "update-ref", "refs/remotes/origin/trunk", "HEAD")
    _git(
        repo,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/trunk",
    )
    assert trunk_of(repo) == "origin/trunk"
    _git(repo, "checkout", "-q", "-b", "work")
    _commit(repo, "w")
    assert [(n, a) for n, a, _ in branch_work(repo)] == [("work", 1)]


def test_a_repo_with_no_trunk_and_a_plain_directory_give_nothing(
    tmp_path: Path,
) -> None:
    """No main to count from, and no git at all, are empty, never a zero or an error."""
    odd = _repo(tmp_path / "odd", trunk="elsewhere")
    _git(odd, "checkout", "-q", "-b", "feature")
    _commit(odd, "f")
    assert branch_work(odd) == []
    plain = tmp_path / "plain"
    plain.mkdir()
    assert branch_work(plain) == []


def _fleet(root: Path, repo: str, *, with_git: bool) -> None:
    """Make one workstream directory, with a .git directory when asked."""
    (root / repo / ".claude").mkdir(parents=True)
    (root / repo / ".claude" / "paths-forward.json").write_text("{}", encoding="utf-8")
    if with_git:
        (root / repo / ".git").mkdir()


def _fake(_top: Path) -> list[tuple[str, int, int]]:
    """Stand for branch_work: one branch, three commits ahead.

    Returns:
        One row.

    """
    return [("feature/x", 3, 1700000000)]


def test_the_gauges_name_the_repo_and_the_branch(tmp_path: Path) -> None:
    """Each current branch gets both samples; a repo with no .git gets none."""
    _fleet(tmp_path, "demo", with_git=True)
    _fleet(tmp_path, "nogit", with_git=False)
    lines = branch_lines(tmp_path, read=_fake)
    tags = label(repo="demo", branch="feature/x")
    assert f"nemik_branch_commits_ahead{tags} 3" in lines
    assert f"nemik_branch_newest_commit_seconds{tags} 1700000000" in lines
    assert not any("nogit" in line for line in lines)
    assert "# TYPE nemik_branch_commits_ahead gauge" in lines
