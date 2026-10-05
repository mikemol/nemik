"""nemik:W224: a workstream may contain others, so a root with its own queue is one too."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nemik.check import QUEUE, workstream_files

if TYPE_CHECKING:
    from pathlib import Path

STATE = '{"version": 1, "counter": 0, "waypoints": [], "residue": []}\n'


def _queue(at: Path) -> Path:
    """Write an empty queue under `at/.claude`.

    Returns:
        The queue file's path.

    """
    path = at / ".claude" / QUEUE
    path.parent.mkdir(parents=True)
    path.write_text(STATE, encoding="utf-8")
    return path


def test_a_root_queue_is_a_workstream_beside_its_children(tmp_path: Path) -> None:
    """The host queue over the repos is `<root dir name>`, found with each repo."""
    root = tmp_path / "github"
    root.mkdir()
    _queue(root)
    _queue(root / "alpha")
    _queue(root / "beta")
    got = workstream_files(root, QUEUE)
    assert [name for name, _ in got] == ["alpha", "beta", "github"]


def test_a_root_with_no_queue_of_its_own_adds_no_workstream(tmp_path: Path) -> None:
    """Only the children are found, as before."""
    root = tmp_path / "github"
    _queue(root / "alpha")
    assert [name for name, _ in workstream_files(root, QUEUE)] == ["alpha"]


def test_a_root_pointed_at_one_repo_is_that_repo(tmp_path: Path) -> None:
    """The old fallback is the same rule with nothing beneath the root."""
    root = tmp_path / "solo"
    path = _queue(root)
    assert workstream_files(root, QUEUE) == [("solo", path)]


def test_a_child_with_the_roots_own_name_wins(tmp_path: Path) -> None:
    """A repo named like its parent directory keeps its name for its own queue."""
    root = tmp_path / "github"
    _queue(root)
    child = _queue(root / "github")
    assert workstream_files(root, QUEUE) == [("github", child)]
