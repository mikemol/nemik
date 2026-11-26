# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2044: the process's own command line is the words after the program name."""

import pytest

from nemik.flags import command_line


def test_the_program_name_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """sys.argv[0] is the program, never a flag or a positional word."""
    monkeypatch.setattr("sys.argv", ["nemik-metrics", "--root", "/x", "word"])
    assert command_line() == ["--root", "/x", "word"]
    monkeypatch.setattr("sys.argv", ["nemik-metrics"])
    assert command_line() == []
