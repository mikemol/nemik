# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1851: nemik-metrics reads its command line with nemik.flags, as argparse read it."""

from pathlib import Path

import pytest

from nemik.metrics import BAD_USAGE, read_options, spool_path
from nemik.queuefiles import default_root


def test_no_flags_read_the_defaults() -> None:
    """Each option defaults as argparse did: the real root and spool, no runs, no family."""
    options = read_options([])
    assert options.root == default_root()
    assert options.spool == spool_path()
    assert options.runs is None
    assert options.family is None


def test_every_flag_is_read_as_a_path_or_a_repeated_family() -> None:
    """The space and equals forms both read; --family repeats."""
    options = read_options(
        ["--root=/r", "--spool", "/s", "--runs", "/x", "--family", "a", "--family=b"]
    )
    assert options.root == Path("/r")
    assert options.spool == Path("/s")
    assert options.runs == Path("/x")
    assert options.family == ["a", "b"]


def test_help_prints_the_usage_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--help and -h print usage on stdout and exit 0."""
    for word in ("--help", "-h"):
        with pytest.raises(SystemExit) as raised:
            read_options([word])
        assert raised.value.code == 0
        assert "usage: nemik-metrics" in capsys.readouterr().out


def test_a_bad_command_line_exits_two_and_says_why(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """MUTANT: running on after an unknown flag would answer for a typo; it exits 2."""
    for line, why in (
        (["--bogus"], "unrecognized argument: --bogus"),
        (["stray"], "unrecognized argument: stray"),
        (["--root"], "--root: expected one argument"),
    ):
        with pytest.raises(SystemExit) as raised:
            read_options(line)
        assert raised.value.code == BAD_USAGE
        assert why in capsys.readouterr().err
