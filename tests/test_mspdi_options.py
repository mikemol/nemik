# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1856: nemik-export reads its command line with nemik.flags, as argparse read it."""

from pathlib import Path

import pytest

from nemik.mspdi import BAD_USAGE, read_options
from nemik.queuefiles import default_root

EVERY_FLAG = [
    "--root=/r",
    "--repo",
    "a",
    "--repo=b",
    "--format",
    "issues",
    "--against",
    "/t",
]


def test_no_flags_read_the_defaults() -> None:
    """The real root, every repo, the MSPDI format, no tracker file."""
    options = read_options([])
    assert options.root == default_root()
    assert options.repo == []
    assert options.format == "mspdi"
    assert options.against is None


def test_every_flag_is_read() -> None:
    """The space and equals forms both read; --repo repeats."""
    options = read_options(EVERY_FLAG)
    assert options.root == Path("/r")
    assert options.repo == ["a", "b"]
    assert options.format == "issues"
    assert options.against == Path("/t")


def test_help_prints_the_usage_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--help prints usage on stdout and exits 0."""
    with pytest.raises(SystemExit) as raised:
        read_options(["--help"])
    assert raised.value.code == 0
    assert "usage: nemik-export" in capsys.readouterr().out


def test_a_bad_command_line_exits_two_and_says_why(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """MUTANT: a format outside the two choices must not fall through to mspdi."""
    for line, why in (
        (["--format", "csv"], "invalid choice: 'csv'"),
        (["--bogus"], "unrecognized argument: --bogus"),
        (["stray"], "unrecognized argument: stray"),
        (["--against"], "--against: expected one argument"),
    ):
        with pytest.raises(SystemExit) as raised:
            read_options(line)
        assert raised.value.code == BAD_USAGE
        assert why in capsys.readouterr().err
