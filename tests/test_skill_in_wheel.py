# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2386: the nemik skill ships inside the wheel, byte for byte, at nemik/skills/nemik/."""

import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

from mikemol.procrun.proc import capture

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "nemik"
PYPROJECT = ROOT / "pyproject.toml"
INSIDE = "nemik/skills/nemik/"
FORCE_INCLUDE = '"skills/nemik" = "nemik/skills/nemik"\n'


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source() -> dict[str, str]:
    """Give the skill directory's files as the wheel should hold them.

    Returns:
        The in-wheel name of each file under skills/nemik, and its sha256.

    """
    return {
        INSIDE + path.relative_to(SKILL).as_posix(): _digest(path.read_bytes())
        for path in sorted(SKILL.rglob("*"))
        if path.is_file()
    }


def _wheel_skill(tmp_path: Path, pyproject: str) -> dict[str, str]:
    """Build a wheel with the project's own build backend and list the skill it holds.

    The tree is minimal: the real pyproject text, an empty package and the real skill
    directory. What is under test is the packaging rule, not the package.

    Returns:
        The in-wheel name of each file under nemik/skills/nemik/, and its sha256.

    """
    tree = tmp_path / "tree"
    (tree / "src" / "nemik").mkdir(parents=True)
    (tree / "src" / "nemik" / "__init__.py").write_text("", encoding="utf-8")
    shutil.copytree(SKILL, tree / "skills" / "nemik")
    (tree / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    out = tmp_path / "out"
    argv = [sys.executable, "-m", "hatchling", "build", "-t", "wheel", "-d", str(out)]
    done = capture(argv, cwd=tree)
    assert done.returncode == 0, done.stdout + done.stderr
    (wheel,) = out.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        return {
            name: _digest(archive.read(name))
            for name in archive.namelist()
            if name.startswith(INSIDE) and not name.endswith("/")
        }


def test_the_wheel_carries_the_skill_directory_byte_for_byte(tmp_path: Path) -> None:
    """Every file under skills/nemik is in the wheel at nemik/skills/nemik/, nothing more."""
    held = _wheel_skill(tmp_path, PYPROJECT.read_text(encoding="utf-8"))
    assert held == _source()
    assert INSIDE + "SKILL.md" in held


def test_without_the_force_include_the_wheel_holds_no_skill(tmp_path: Path) -> None:
    """The planted drill: the rule removed, the test's measurement goes empty, so it can fail."""
    text = PYPROJECT.read_text(encoding="utf-8")
    assert FORCE_INCLUDE in text
    held = _wheel_skill(tmp_path, text.replace(FORCE_INCLUDE, ""))
    assert held != _source()
    assert not held
