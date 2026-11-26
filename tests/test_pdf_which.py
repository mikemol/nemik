# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1871: nemik.pdf finds rsvg-convert on PATH without shutil, and says where it looked."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from nemik.pdf import search_path

if TYPE_CHECKING:
    from pathlib import Path

EXE = 0o755
PLAIN = 0o644


def _tool(directory: Path, name: str, mode: int) -> Path:
    """Write a file called name with a mode.

    Returns:
        The file's path.

    """
    path = directory / name
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(mode)
    return path


def test_the_first_executable_on_path_is_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two directories hold the tool; the earlier one wins, as in shutil.which."""
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    found = _tool(first, "rsvg-convert", EXE)
    _tool(second, "rsvg-convert", EXE)
    monkeypatch.setenv("PATH", f"{first}:{second}")
    answer = search_path("rsvg-convert")
    assert answer.found
    assert answer.executable == str(found)
    assert shutil.which("rsvg-convert") == str(found)


def test_a_file_that_is_not_executable_is_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MUTANT: taking any file of that name would run a document."""
    _tool(tmp_path, "rsvg-convert", PLAIN)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert not search_path("rsvg-convert").found
    assert shutil.which("rsvg-convert") is None


def test_a_miss_names_the_directories_it_searched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The answer carries where it looked, in order, for the error message."""
    monkeypatch.setenv("PATH", f"{tmp_path}:/nonexistent")
    answer = search_path("rsvg-convert")
    assert not answer.found
    assert not answer.executable
    assert answer.searched == [str(tmp_path), "/nonexistent"]


def test_an_empty_entry_is_not_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MUTANT: reading '' as '.' would run a same-named file from the working directory."""
    _tool(tmp_path, "rsvg-convert", EXE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", ":")
    answer = search_path("rsvg-convert")
    assert not answer.found
    assert answer.searched == []


def test_an_unset_path_searches_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unlike shutil.which, which falls back to os.defpath, no PATH means no search."""
    monkeypatch.delenv("PATH")
    answer = search_path("rsvg-convert")
    assert not answer.found
    assert answer.searched == []
