# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2365: tools/presubmit.sh is the commit gate run over a review worktree's index."""

import shutil
from pathlib import Path

from mikemol.procrun.proc import capture

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "presubmit.sh"
GATE_CALL = (
    'GIT_INDEX_FILE="$idx" MIKEMOL_REAL_ROOT="$real_root" '
    '"$real_root/tools/gate_staged.sh" || rc=$?'
)
STUB_STATUS = 3


def _git(*args: str) -> str:
    """Run git and fail the test on a nonzero exit.

    Returns:
        Git's stdout, stripped.

    """
    ran = capture(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args])
    assert ran.returncode == 0, ran.stderr
    return ran.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a repository whose gate is a stub that records its input, and a worktree.

    Returns:
        The repository, its linked worktree and the file the stub gate writes.

    """
    repo = tmp_path / "repo"
    seen = tmp_path / "seen.txt"
    _git("init", "-q", "-b", "main", str(repo))
    (repo / "tools").mkdir()
    shutil.copyfile(SCRIPT, repo / "tools" / "presubmit.sh")
    stub = repo / "tools" / "gate_staged.sh"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n%s\\n' \"$GIT_INDEX_FILE\" \"$MIKEMOL_REAL_ROOT\" > '{seen}'\n"
        f"exit {STUB_STATUS}\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git("-C", str(repo), "add", "-A")
    _git("-C", str(repo), "commit", "-q", "-m", "base")
    wt = tmp_path / "wt"
    _git("-C", str(repo), "worktree", "add", "-q", "--detach", str(wt))
    return repo, wt, seen


def _presubmit(repo: Path, wt: Path) -> tuple[int, str, str]:
    """Run the repository's presubmit.sh from its root on a worktree.

    Returns:
        The exit status, stdout and stderr.

    """
    script = str(repo / "tools" / "presubmit.sh")
    ran = capture(["bash", script, str(wt)], cwd=repo)
    return ran.returncode, ran.stdout, ran.stderr


def test_the_gate_judges_the_worktree_index(tmp_path: Path) -> None:
    """The gate sees the worktree's index and the real root; its status is kept."""
    repo, wt, seen = _repo(tmp_path)
    (wt / "a.txt").write_text("changed\n", encoding="utf-8")
    _git("-C", str(wt), "add", "-A")
    status, out, _ = _presubmit(repo, wt)
    assert status == STUB_STATUS
    where = ("rev-parse", "--path-format=absolute", "--git-path", "index")
    index = _git("-C", str(wt), *where)
    assert seen.read_text(encoding="utf-8").splitlines() == [index, str(repo)]
    tree = _git("-C", str(wt), "write-tree")
    assert out.splitlines() == [f"tree {tree} rc {STUB_STATUS}"]


def test_a_directory_that_is_no_worktree_of_this_repo_is_refused(
    tmp_path: Path,
) -> None:
    """Another repository's checkout never reaches the gate."""
    repo, _, seen = _repo(tmp_path)
    other = tmp_path / "other"
    _git("init", "-q", "-b", "main", str(other))
    status, _, err = _presubmit(repo, other)
    assert status == 1
    assert "is not a worktree of" in err
    assert not seen.exists()


def test_an_unstaged_change_is_refused(tmp_path: Path) -> None:
    """The gate judges the index, so an unstaged change is not the tree under review."""
    repo, wt, seen = _repo(tmp_path)
    (wt / "a.txt").write_text("changed\n", encoding="utf-8")
    status, _, err = _presubmit(repo, wt)
    assert status == 1
    assert "unstaged changes" in err
    assert not seen.exists()


def test_an_untracked_file_is_refused(tmp_path: Path) -> None:
    """A new file not staged is refused the same way."""
    repo, wt, seen = _repo(tmp_path)
    (wt / "new.txt").write_text("n\n", encoding="utf-8")
    status, _, err = _presubmit(repo, wt)
    assert status == 1
    assert "untracked files" in err
    assert not seen.exists()


def test_the_only_gate_it_runs_is_gate_staged() -> None:
    """One whole non-comment line calls the gate; nothing runs bazel or its own step."""
    code = [
        line.strip()
        for line in SCRIPT.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert [line for line in code if "gate_staged" in line] == [GATE_CALL]
    assert not [line for line in code if "bazel" in line]
