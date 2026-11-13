# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2179: calendars finds a command on PATH and removes its scratch directory without shutil.

shutil is a Codon wall and calendars.py was the one module carrying it. on_path and remove_scratch
replace shutil.which and shutil.rmtree(ignore_errors=True) for what calendars needs of them, and the
tests compare on_path with shutil.which on the cases that matter.
"""

import os
import shutil
import stat
from typing import TYPE_CHECKING

import pytest

from nemik.calendars import on_path, remove_scratch

if TYPE_CHECKING:
    from pathlib import Path


def _command(folder: Path, name: str, *, executable: bool) -> Path:
    """Write a command file into `folder`.

    Returns:
        The file.

    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755 if executable else 0o644)
    return path


def test_an_executable_on_path_is_found_as_which_finds_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Find a command in a PATH directory, with the answer shutil.which gives."""
    _command(tmp_path / "bin", "nemik-fake-ics", executable=True)
    monkeypatch.setenv("PATH", f"{tmp_path / 'missing'}{os.pathsep}{tmp_path / 'bin'}")
    assert on_path("nemik-fake-ics") is True
    assert shutil.which("nemik-fake-ics") is not None


def test_a_file_that_is_not_executable_is_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skip a PATH file without the execute bit, as shutil.which does."""
    _command(tmp_path / "bin", "nemik-fake-ics", executable=False)
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    assert on_path("nemik-fake-ics") is False
    assert shutil.which("nemik-fake-ics") is None


def test_a_missing_command_and_an_empty_path_are_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Report False for a command no PATH directory holds, and for an empty PATH."""
    monkeypatch.setenv("PATH", str(tmp_path))
    assert on_path("nemik-fake-ics") is False
    monkeypatch.setenv("PATH", "")
    assert on_path("nemik-fake-ics") is False


def test_a_directory_named_like_the_command_is_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skip a directory of that name: it is not a command."""
    (tmp_path / "bin" / "nemik-fake-ics").mkdir(parents=True)
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    assert on_path("nemik-fake-ics") is False


def test_the_scratch_directory_and_its_files_are_removed(tmp_path: Path) -> None:
    """Remove the directory with the files an interrupted run left in it."""
    scratch = tmp_path / "nemik-cal-x"
    scratch.mkdir()
    (scratch / "a.ics").write_text("x", encoding="utf-8")
    (scratch / "b.ics").write_text("y", encoding="utf-8")
    remove_scratch(scratch)
    assert not scratch.exists()


def test_removing_a_missing_directory_is_silent(tmp_path: Path) -> None:
    """Ignore a directory that is already gone, as rmtree(ignore_errors=True) does."""
    remove_scratch(tmp_path / "never-made")


def test_a_directory_that_cannot_be_emptied_is_left_without_raising(tmp_path: Path) -> None:
    """Leave a non-empty subdirectory alone and say nothing: the temp cleaner has the rest."""
    scratch = tmp_path / "nemik-cal-y"
    (scratch / "nested").mkdir(parents=True)
    (scratch / "nested" / "kept.ics").write_text("z", encoding="utf-8")
    scratch.chmod(stat.S_IRWXU)
    remove_scratch(scratch)
    assert (scratch / "nested").exists()
