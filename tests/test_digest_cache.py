# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W763: an unchanged fleet answers the per-prompt digest from the last run."""

from pathlib import Path

import pytest
from rdflib import Graph

from nemik import cachestore, check

QUEUE = '{"waypoints": [], "residue": []}'


def _root(tmp_path: Path) -> Path:
    """Make a fleet root with one repo that has a queue and a ledger.

    Returns:
        The root.

    """
    claude = tmp_path / "root" / "a" / ".claude"
    claude.mkdir(parents=True)
    (claude / check.QUEUE).write_text(QUEUE, encoding="utf-8")
    (claude / check.LEDGER).write_text("", encoding="utf-8")
    return tmp_path / "root"


def _key(root: Path, *, digest: bool = True) -> str:
    """Name the inputs of a survey of this root.

    Returns:
        The content key.

    """
    return cachestore.content_key(check.survey_inputs(root, digest=digest))


def test_the_key_follows_the_content_of_the_queue_and_the_mode(tmp_path: Path) -> None:
    """Same files, same key; a changed queue or the other mode, another."""
    root = _root(tmp_path)
    first = _key(root)
    assert first == _key(root)
    assert first != _key(root, digest=False)
    queue = root / "a" / ".claude" / check.QUEUE
    queue.write_text(QUEUE.replace("[]", "[ ]", 1), encoding="utf-8")
    assert first != _key(root)


def test_each_outside_read_of_the_survey_is_in_the_key(tmp_path: Path) -> None:
    """The host-apply export, the loop prompt, a repo's pyproject and an inbox each change it."""
    root = _root(tmp_path)
    first = _key(root)
    (root / "host-apply.json").write_text("{}", encoding="utf-8")
    second = _key(root)
    assert second != first
    (root / ".claude").mkdir()
    (root / ".claude" / "loop-prompt.md").write_text("tick", encoding="utf-8")
    third = _key(root)
    assert third != second
    (root / "a" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    fourth = _key(root)
    assert fourth != third
    (root / "a" / "inbox").mkdir()
    (root / "a" / "inbox" / "letter.md").write_text("hi", encoding="utf-8")
    assert _key(root) != fourth


def test_an_unchanged_fleet_is_surveyed_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second call reads the stored answer; a changed queue surveys again."""
    root = _root(tmp_path)
    calls: list[int] = []

    def survey(_root: Path, *, digest: bool) -> tuple[list[str], int, Graph]:
        calls.append(int(digest))
        return ["OK        a"], 0, Graph()

    monkeypatch.setenv("NEMIK_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(check, "default_root", lambda: root)
    monkeypatch.setattr(check, "survey_lines", survey)
    assert check.cached_survey(root, digest=True) == (["OK        a"], 0)
    assert check.cached_survey(root, digest=True) == (["OK        a"], 0)
    assert len(calls) == 1
    queue = root / "a" / ".claude" / check.QUEUE
    queue.write_text(QUEUE.replace("[]", "[ ]", 1), encoding="utf-8")
    check.cached_survey(root, digest=True)
    assert len(calls) == len(("first", "after the change"))
