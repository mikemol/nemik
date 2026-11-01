# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1384: the output module writes a line to stdout, raw text to stdout, a line to stderr."""

import pytest

from nemik.say import say, say_raw, warn


def test_say_writes_one_line_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """A line goes to stdout with its newline, and nothing goes to stderr."""
    say("hello")
    say()
    seen = capsys.readouterr()
    assert seen.out == "hello\n\n"
    assert not seen.err


def test_say_raw_adds_no_newline(capsys: pytest.CaptureFixture[str]) -> None:
    """Raw text reaches stdout exactly as given."""
    say_raw("a")
    say_raw("b\n")
    assert capsys.readouterr().out == "ab\n"


def test_warn_writes_to_stderr_only(capsys: pytest.CaptureFixture[str]) -> None:
    """A warning is a stderr line and leaves stdout empty."""
    warn("careful")
    seen = capsys.readouterr()
    assert seen.err == "careful\n"
    assert not seen.out
