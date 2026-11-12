# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2139: an undecodable pyproject.toml is read as a file that declares nothing, not a crash.

adoption_state catches (OSError, ValueError) where it caught (OSError, tomllib.TOMLDecodeError).
A ValueError covers the toml error and also the UnicodeDecodeError that read_text raises for bytes
that are not text, which used to propagate. (The pinned mypy also sees Any in the TOMLDecodeError
stub type at Python 3.14, nemik:W2125.)
"""


from typing import TYPE_CHECKING

from nemik.check import adoption_state

if TYPE_CHECKING:
    from pathlib import Path

BAD_BYTES = b"\xff\xfe\x00\x80"
NOT_TOML = "this is [not toml"


def _queue(repo: Path) -> Path:
    """Make the repository's .claude directory and name its queue file.

    Returns:
        The queue path whose parent is the .claude directory.

    """
    (repo / ".claude").mkdir(parents=True)
    return repo / ".claude" / "paths-forward.json"


def test_an_undecodable_root_pyproject_is_missing(tmp_path: Path) -> None:
    """Bytes that are not UTF-8 in the root pyproject.toml read as missing, not as a crash."""
    queue = _queue(tmp_path)
    (tmp_path / "pyproject.toml").write_bytes(BAD_BYTES)
    assert adoption_state(queue) == "missing"


def test_a_malformed_root_pyproject_is_still_missing(tmp_path: Path) -> None:
    """A toml error was caught before and still is."""
    queue = _queue(tmp_path)
    (tmp_path / "pyproject.toml").write_text(NOT_TOML, encoding="utf-8")
    assert adoption_state(queue) == "missing"


def test_an_undecodable_sibling_pyproject_is_skipped(tmp_path: Path) -> None:
    """A subdirectory's undecodable pyproject.toml is skipped, and the root decides."""
    queue = _queue(tmp_path)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "pyproject.toml").write_bytes(BAD_BYTES)
    assert adoption_state(queue) == "no-pyproject"
