# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1670: the venv's installed nemik lists the same modules as the tree.

checks/claims.py imports nemik from the venv, not from the tree, so a module added to the tree is
missing there until `./setup.sh` rebuilds the venv (nemik:W1669: all 20 architecture claims failed
on the new queuefiles module, with a bare ModuleNotFoundError). This names the cause first.
"""

import sysconfig
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parents[1] / "src" / "nemik"


def _stems(folder: Path) -> set[str]:
    return {p.stem for p in folder.glob("*.py")}


def missing_modules(tree: Path, installed: Path) -> list[str]:
    """Name the modules the tree has and the installed copy lacks.

    Returns:
        The sorted module names present in `tree` and absent from `installed`.

    """
    return sorted(_stems(tree) - _stems(installed))


def test_the_installed_package_has_every_module_of_the_tree() -> None:
    """A stale venv is named, with its repair, before any claim imports from it."""
    installed = Path(sysconfig.get_paths()["purelib"]) / "nemik"
    if not installed.is_dir() or not TREE.is_dir():
        pytest.skip("no installed nemik beside this tree")
    gone = missing_modules(TREE, installed)
    assert not gone, f"the venv's nemik lacks {gone}: run ./setup.sh"


def test_a_module_missing_from_the_installed_copy_is_named(tmp_path: Path) -> None:
    """Two folders that differ by one module report exactly that module."""
    tree, installed = tmp_path / "tree", tmp_path / "installed"
    tree.mkdir()
    installed.mkdir()
    for name in ("a.py", "b.py"):
        (tree / name).write_text("", encoding="utf-8")
    (installed / "a.py").write_text("", encoding="utf-8")
    assert missing_modules(tree, installed) == ["b"]
    assert missing_modules(installed, tree) == []
