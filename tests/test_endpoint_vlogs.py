# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W774: vlogs_lines refuses, with OSError, when luthen's query tool is not there."""

from pathlib import Path

import pytest

from nemik.endpoint import vlogs_lines


def test_a_missing_luthen_checkout_raises(tmp_path: Path) -> None:
    """No checkout under the root, nothing to run: the caller learns it cannot answer."""
    with pytest.raises(OSError, match="vlogs_query"):
        vlogs_lines("stream:host_root_frontier", tmp_path)


def test_a_failing_tool_raises(tmp_path: Path) -> None:
    """A checkout whose vlogs_query exits non-zero is an OSError, not an empty answer."""
    package = tmp_path / "luthen-observability" / "checks"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "vlogs_query.py").write_text("raise SystemExit(3)\n", encoding="utf-8")
    with pytest.raises(OSError, match="exited 3"):
        vlogs_lines("stream:host_root_frontier", tmp_path)


def test_a_working_tool_gives_its_lines(tmp_path: Path) -> None:
    """The answer is the tool's stdout, one record per line."""
    package = tmp_path / "luthen-observability" / "checks"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "vlogs_query.py").write_text(
        'print("a")\nprint("b")\n', encoding="utf-8"
    )
    assert vlogs_lines("q", tmp_path) == ["a", "b"]
