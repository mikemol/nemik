# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2252: a queue that stays modified is visible, from git metadata and a first-seen mark."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from mikemol.procrun.proc import capture

from nemik.history import CLEAN, DIRTY, UNKNOWN, dirty_for, queue_state
from nemik.metrics import label, queue_dirty_lines

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "PATH": "/usr/bin:/bin",
}
QUEUE = ".claude/paths-forward.json"
LEDGER = ".claude/paths-forward.ledger"
THIRTY = 30


def _git(repo: Path, *args: str) -> None:
    """Run git in `repo` as a fixed author and fail the test on an error."""
    done = capture(["git", "-C", str(repo), *args], env=ENV)
    assert done.returncode == 0, done.stderr


def _repo(path: Path) -> Path:
    """Start a repository with the queue and its ledger committed on main.

    Returns:
        The repository's directory.

    """
    (path / ".claude").mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    (path / QUEUE).write_text("{}", encoding="utf-8")
    (path / LEDGER).write_text("", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "queue")
    return path


def test_a_committed_queue_is_clean(tmp_path: Path) -> None:
    """Nothing differs from HEAD."""
    assert queue_state(_repo(tmp_path / "r")) == CLEAN


def test_a_modified_queue_or_ledger_or_a_new_queue_file_is_dirty(
    tmp_path: Path,
) -> None:
    """Either file differing from HEAD is dirty, and so is a queue never committed."""
    repo = _repo(tmp_path / "r")
    (repo / QUEUE).write_text('{"edited": true}', encoding="utf-8")
    assert queue_state(repo) == DIRTY
    _git(repo, "checkout", "--", QUEUE)
    assert queue_state(repo) == CLEAN
    (repo / LEDGER).write_text("a tick line\n", encoding="utf-8")
    assert queue_state(repo) == DIRTY
    fresh = tmp_path / "fresh"
    (fresh / ".claude").mkdir(parents=True)
    _git(fresh, "init", "-q", "-b", "main")
    (fresh / QUEUE).write_text("{}", encoding="utf-8")
    assert queue_state(fresh) == DIRTY


def test_a_change_to_another_file_does_not_make_the_queue_dirty(
    tmp_path: Path,
) -> None:
    """Only the queue and its ledger count: queue discipline is about them."""
    repo = _repo(tmp_path / "r")
    (repo / "notes.txt").write_text("x", encoding="utf-8")
    assert queue_state(repo) == CLEAN


def test_a_directory_with_no_git_is_unknown_never_clean(tmp_path: Path) -> None:
    """Git cannot answer, so the state is UNKNOWN, a state of its own."""
    plain = tmp_path / "plain"
    plain.mkdir()
    assert queue_state(plain) == UNKNOWN
    assert UNKNOWN not in {CLEAN, DIRTY}


def test_the_clock_starts_at_the_first_dirty_scrape_and_a_clean_one_stops_it(
    tmp_path: Path,
) -> None:
    """First sight is 0 seconds, later scrapes count from it, a clean scrape removes it."""
    mark = tmp_path / "marks" / "demo.since"
    assert dirty_for(mark, dirty=True, now=1000) == 0
    assert mark.read_text(encoding="utf-8") == "1000"
    assert dirty_for(mark, dirty=True, now=1000 + THIRTY) == THIRTY
    assert mark.read_text(encoding="utf-8") == "1000"
    assert dirty_for(mark, dirty=False, now=1100) == 0
    assert not mark.exists()
    assert dirty_for(mark, dirty=True, now=1200) == 0


def test_a_mark_that_is_not_a_number_restarts_the_clock(tmp_path: Path) -> None:
    """A damaged first-seen file is never read as an old clock."""
    mark = tmp_path / "demo.since"
    mark.write_text("not a time", encoding="utf-8")
    assert dirty_for(mark, dirty=True, now=5000) == 0
    assert mark.read_text(encoding="utf-8") == "5000"


def _fleet(root: Path, repo: str, *, with_git: bool) -> None:
    """Make one workstream directory, with a .git directory when asked."""
    (root / repo / ".claude").mkdir(parents=True)
    (root / repo / ".claude" / "paths-forward.json").write_text("{}", encoding="utf-8")
    if with_git:
        (root / repo / ".git").mkdir()


def _says(state: str) -> Callable[[Path], str]:
    """Stand for history.queue_state with one fixed answer.

    Returns:
        A reader that always gives `state`.

    """

    def read(_top: Path) -> str:
        """Give the fixed state.

        Returns:
            The state this reader was made with.

        """
        return state

    return read


def _scrape(root: Path, seconds: int, state: str) -> list[str]:
    """Run one scrape at a Unix time, every repo reading as `state`.

    Returns:
        The scrape's lines.

    """
    when = datetime.fromtimestamp(seconds, UTC)
    return queue_dirty_lines(root, when, read=_says(state), marks=root / "marks")


def test_the_gauges_name_the_repo_and_count_up_across_scrapes(tmp_path: Path) -> None:
    """The flag is 1 and the seconds grow from the first scrape."""
    _fleet(tmp_path, "demo", with_git=True)
    tags = label(repo="demo")
    one = _scrape(tmp_path, 2000, DIRTY)
    two = _scrape(tmp_path, 2000 + THIRTY, DIRTY)
    assert f"nemik_queue_dirty{tags} 1" in one
    assert f"nemik_queue_dirty_seconds{tags} 0" in one
    assert f"nemik_queue_dirty_seconds{tags} {THIRTY}" in two
    for name in ("nemik_queue_dirty", "nemik_queue_dirty_seconds"):
        assert f"# TYPE {name} gauge" in one
    assert "# TYPE nemik_queue_dirty_unknown gauge" in one


def test_a_repo_that_cannot_be_read_prints_its_own_unknown_sample(
    tmp_path: Path,
) -> None:
    """A repo with no .git, and one git refuses, each print unknown 1 and no dirty sample."""
    _fleet(tmp_path, "nogit", with_git=False)
    _fleet(tmp_path, "refused", with_git=True)
    lines = _scrape(tmp_path, 3000, UNKNOWN)
    dirty = ("nemik_queue_dirty{", "nemik_queue_dirty_seconds{")
    for repo in ("nogit", "refused"):
        assert f"nemik_queue_dirty_unknown{label(repo=repo)} 1" in lines
        assert not [x for x in lines if x.startswith(dirty) and repo in x]


def test_an_unknown_scrape_neither_starts_nor_resets_the_clock(tmp_path: Path) -> None:
    """Dirty at 2000, unknown at 2010, dirty at 2030: the clock still reads 30 seconds."""
    _fleet(tmp_path, "demo", with_git=True)
    tags = label(repo="demo")
    _scrape(tmp_path, 2000, DIRTY)
    unknown = _scrape(tmp_path, 2010, UNKNOWN)
    assert f"nemik_queue_dirty_unknown{tags} 1" in unknown
    last = _scrape(tmp_path, 2000 + THIRTY, DIRTY)
    assert f"nemik_queue_dirty_seconds{tags} {THIRTY}" in last
