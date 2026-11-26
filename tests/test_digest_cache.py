# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W763: an unchanged fleet answers the per-prompt digest from the last run."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rdflib import Graph

from nemik import cachestore, check, queuefiles

if TYPE_CHECKING:
    from pathlib import Path

QUEUE = '{"waypoints": [], "residue": []}'


def _root(tmp_path: Path) -> Path:
    """Make a fleet root with one repo that has a queue and a ledger.

    Returns:
        The root.

    """
    claude = tmp_path / "root" / "a" / ".claude"
    claude.mkdir(parents=True)
    (claude / queuefiles.QUEUE).write_text(QUEUE, encoding="utf-8")
    (claude / queuefiles.LEDGER).write_text("", encoding="utf-8")
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
    queue = root / "a" / ".claude" / queuefiles.QUEUE
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
    queue = root / "a" / ".claude" / queuefiles.QUEUE
    queue.write_text(QUEUE.replace("[]", "[ ]", 1), encoding="utf-8")
    check.cached_survey(root, digest=True)
    assert len(calls) == len(("first", "after the change"))


def test_the_warning_rows_of_an_unchanged_fleet_are_surveyed_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """nemik:W2511: --repo X --warnings ran the whole survey every time.

    An unchanged fleet now answers from the stored rows; a changed queue or an unreadable cache
    surveys again.
    """
    root = _root(tmp_path)
    calls: list[str] = []
    answer = {"a": (["OK        a", "Warning   W1 waits"], 0)}

    def rows(_root: Path) -> dict[str, tuple[list[str], int]]:
        calls.append("survey")
        return answer

    cache = tmp_path / "cache"
    monkeypatch.setenv("NEMIK_CACHE_DIR", str(cache))
    monkeypatch.setattr(check, "default_root", lambda: root)
    monkeypatch.setattr(check, "warning_rows", rows)
    assert check.cached_warning_rows(root) == answer
    assert check.cached_warning_rows(root) == answer
    assert len(calls) == 1
    queue = root / "a" / ".claude" / queuefiles.QUEUE
    queue.write_text(QUEUE.replace("[]", "[ ]", 1), encoding="utf-8")
    check.cached_warning_rows(root)
    assert len(calls) == len(("first", "after the change"))
    (cache / check.WARNINGS_FILE).write_text("not json", encoding="utf-8")
    assert check.cached_warning_rows(root) == answer
    assert len(calls) == len(("first", "after the change", "after the bad cache"))


def test_a_root_that_is_not_the_fleet_is_never_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Like cached_survey, only the real fleet root is kept: another root surveys every time."""
    root = _root(tmp_path)
    calls: list[str] = []

    def rows(_root: Path) -> dict[str, tuple[list[str], int]]:
        calls.append("survey")
        return {}

    monkeypatch.setenv("NEMIK_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(check, "default_root", lambda: tmp_path / "elsewhere")
    monkeypatch.setattr(check, "warning_rows", rows)
    check.cached_warning_rows(root)
    check.cached_warning_rows(root)
    assert len(calls) == len(("first", "second"))
