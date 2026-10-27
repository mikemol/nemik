# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W730: a stale or missing installed module is named, a matching install is clean."""

from pathlib import Path

import pytest

from nemik.stale import STALE_EXIT, USAGE_EXIT, check, stale_modules


def _tree(root: Path, files: dict[str, str]) -> Path:
    root.mkdir()
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def test_a_matching_install_is_clean(tmp_path: Path) -> None:
    """Same files, same text: nothing is stale."""
    files = {"a.py": "x = 1\n", "b.py": "y = 2\n"}
    source = _tree(tmp_path / "src", files)
    installed = _tree(tmp_path / "site", files)
    assert stale_modules(source, installed) == []


def test_a_changed_and_a_missing_module_are_named_sorted(tmp_path: Path) -> None:
    """b.py differs and c.py is not installed; a.py matches; a non-module file is ignored."""
    source = _tree(
        tmp_path / "src",
        {"a.py": "x = 1\n", "b.py": "y = 2\n", "c.py": "z = 3\n", "notes.txt": "n"},
    )
    installed = _tree(tmp_path / "site", {"a.py": "x = 1\n", "b.py": "y = 99\n"})
    assert stale_modules(source, installed) == ["b.py", "c.py"]


def test_the_command_exits_one_and_prints_each_stale_module(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 1 with a STALE line per module; 0 and silence when the install matches."""
    source = _tree(tmp_path / "src", {"a.py": "x = 1\n", "b.py": "y = 2\n"})
    installed = _tree(tmp_path / "site", {"a.py": "x = 1\n", "b.py": "old\n"})
    assert check([str(source), str(installed)]) == STALE_EXIT
    assert capsys.readouterr().out == "STALE b.py\n"
    (installed / "b.py").write_text("y = 2\n", encoding="utf-8")
    assert check([str(source), str(installed)]) == 0
    assert not capsys.readouterr().out


def test_a_wrong_command_line_or_a_missing_directory_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not two arguments, or a directory that does not exist, is a usage error, not stale."""
    assert check([]) == USAGE_EXIT
    assert "usage" in capsys.readouterr().out
    assert check([str(tmp_path), str(tmp_path / "absent")]) == USAGE_EXIT
    assert "not a directory" in capsys.readouterr().out
