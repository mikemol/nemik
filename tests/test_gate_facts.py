# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2344: tools/gate_facts.sh writes the staged tree's git facts, stamped."""

import shutil
from pathlib import Path

import pytest
from hook_facts import parse, parse_diff
from mikemol.procrun.proc import capture

TOOLS = Path(__file__).parent.parent / "tools"
SCRIPT = TOOLS / "gate_facts.sh"
GATE = TOOLS / "gate_staged.sh"
USAGE = 2
NO_TREE = "0" * 40
CHANGED = ["README.md", "src/nemik/b.py"]


def _git(repo: Path, *args: str) -> str:
    """Run git in `repo` as a fixed author and fail the test on an error.

    Returns:
        git's standard output.

    """
    ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
    done = capture(["git", "-C", str(repo), *ident, *args])
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _write(repo: Path, name: str, text: str) -> None:
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(text, encoding="utf-8")


def _read(repo: Path, name: str) -> str:
    return (repo / ".gate-facts" / name).read_text("utf-8")


@pytest.fixture()
def staged(tmp_path: Path) -> tuple[Path, str, str]:
    """Stage a repository with a commit and a second state staged but not committed.

    Returns:
        The repository, the staged tree's sha, and HEAD's sha.

    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    for name in (
        "src/nemik/a.py",
        "tests/test_a.py",
        "vendor/wheels/x.whl",
        "README.md",
    ):
        _write(repo, name, "x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _write(repo, "src/nemik/b.py", "y\n")
    _write(repo, "README.md", "changed\n")
    _git(repo, "add", "-A")
    return repo, _git(repo, "write-tree"), _git(repo, "rev-parse", "HEAD")


def _run(*args: str) -> tuple[int, str]:
    done = capture(["sh", str(SCRIPT), *args])
    return done.returncode, done.stderr


def test_the_facts_are_the_staged_trees_paths_stamped_with_its_sha(
    staged: tuple[Path, str, str],
) -> None:
    """The tracked file holds the tree's paths under the three trees, the changed file the diff."""
    repo, tree, head = staged
    assert _run(str(repo), tree, head) == (0, "")
    tracked = parse(_read(repo, "tracked.txt"), "t")
    changed = parse_diff(_read(repo, "changed.txt"), "c")
    assert (tracked.tree, tracked.head) == (tree, head)
    assert (changed.tree, changed.head) == (tree, head)
    assert tracked.paths == [
        "src/nemik/a.py",
        "src/nemik/b.py",
        "tests/test_a.py",
        "vendor/wheels/x.whl",
    ]
    assert changed.paths == CHANGED
    assert _read(repo, "tracked.txt").splitlines()[0] == "facts tracked"
    assert _read(repo, "changed.txt").splitlines()[0] == "facts changed"


def test_each_facts_file_is_refused_by_the_other_files_parser(
    staged: tuple[Path, str, str],
) -> None:
    """The planted red of nemik:W2350 on the writer's own files: a wrongly wired one is refused."""
    repo, tree, head = staged
    assert _run(str(repo), tree, head)[0] == 0
    with pytest.raises(ValueError, match=r"not 'facts tracked' \('facts changed'\)"):
        parse(_read(repo, "changed.txt"), "changed.txt")
    with pytest.raises(ValueError, match=r"not 'facts changed' \('facts tracked'\)"):
        parse_diff(_read(repo, "tracked.txt"), "tracked.txt")


def test_the_facts_come_from_the_tree_not_the_live_checkout_or_its_index(
    staged: tuple[Path, str, str],
) -> None:
    """Later edits to the working copy and to the index change neither file: only the tree."""
    repo, tree, head = staged
    _write(repo, "src/nemik/untracked.py", "z\n")
    (repo / "src/nemik/a.py").unlink()
    _write(repo, "src/nemik/later.py", "w\n")
    _git(repo, "add", "src/nemik/later.py")
    assert _run(str(repo), tree, head)[0] == 0
    tracked = parse(_read(repo, "tracked.txt"), "t")
    changed = parse_diff(_read(repo, "changed.txt"), "c")
    assert "src/nemik/untracked.py" not in tracked.paths
    assert "src/nemik/later.py" not in tracked.paths
    assert "src/nemik/a.py" in tracked.paths
    assert changed.paths == CHANGED


def test_the_same_tree_against_two_heads_gives_two_stamps_and_two_bodies(
    staged: tuple[Path, str, str],
) -> None:
    """changed.txt is a function of the tree AND the HEAD, so both are stamped."""
    repo, tree, head = staged
    assert _run(str(repo), tree, head)[0] == 0
    first = _read(repo, "changed.txt")
    _git(repo, "commit", "-q", "-m", "second")
    second_head = _git(repo, "rev-parse", "HEAD")
    assert second_head != head
    assert _git(repo, "show", "-s", "--format=%T", "HEAD") == tree
    assert _run(str(repo), tree, second_head)[0] == 0
    second = _read(repo, "changed.txt")
    assert parse_diff(first, "a").head == head
    assert parse_diff(second, "b").head == second_head
    assert parse_diff(first, "a").paths == CHANGED
    assert parse_diff(second, "b").paths == []
    assert first != second


def test_check_passes_on_fresh_facts_and_fails_on_a_stale_or_missing_file(
    staged: tuple[Path, str, str],
) -> None:
    """The freshness check compares the files with what git says now."""
    repo, tree, head = staged
    assert _run("--check", str(repo), tree, head)[0] == 1
    assert _run(str(repo), tree, head)[0] == 0
    assert _run("--check", str(repo), tree, head) == (0, "")
    facts = repo / ".gate-facts" / "changed.txt"
    facts.write_text(facts.read_text("utf-8") + "extra.py\n", encoding="utf-8")
    status, err = _run("--check", str(repo), tree, head)
    assert status == 1
    assert "changed.txt" in err
    assert "not what git says" in err


def test_a_tree_that_is_not_one_writes_nothing(staged: tuple[Path, str, str]) -> None:
    """Git fails, the script fails, and no half-written facts file is left to be read."""
    repo, _, head = staged
    status, _ = _run(str(repo), NO_TREE, head)
    assert status != 0
    assert not (repo / ".gate-facts" / "tracked.txt").exists()
    shutil.rmtree(repo / ".gate-facts", ignore_errors=True)


def test_the_wrong_number_of_arguments_is_a_usage_error() -> None:
    """Nothing is guessed from a short command line."""
    status, err = _run("only-one")
    assert status == USAGE
    assert "usage: gate_facts.sh" in err


def test_the_gate_runs_the_writer_after_read_tree_and_before_bazel() -> None:
    """Deleting, commenting out, weakening or moving the call must fail here."""
    lines = [
        ln.strip()
        for ln in GATE.read_text("utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ]
    call = 'sh "$wt/tools/gate_facts.sh" "$wt" "$tree" "$head_sha" || exit 1'
    assert lines.count(call) == 1
    read_tree = lines.index('git -C "$wt" read-tree --reset -u "$tree" || exit 1')
    venv = next(
        at for at, ln in enumerate(lines) if ln.startswith("bazel build //:.venv")
    )
    assert read_tree < lines.index(call) < venv
