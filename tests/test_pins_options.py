# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1874: nemik-pins reads its command line with nemik.flags, as argparse read it."""

from pathlib import Path

import pytest

from nemik.pins import BAD_USAGE, RECEIPT, STUCK_AFTER, USAGE, VALUED, read_options
from nemik.queuefiles import default_root

LIMITS = ["--max-behind", "3", "--stuck-after", "9"]


def test_no_flags_read_the_defaults() -> None:
    """Every repo, the real root, no limit, the uv receipt, the cluster check on."""
    options = read_options([])
    assert options.repos == []
    assert options.root == default_root()
    assert options.max_behind is None
    assert options.receipt == RECEIPT
    assert options.cluster
    assert options.stuck_after == STUCK_AFTER


def test_every_flag_and_the_repo_words_are_read() -> None:
    """Positional repos, both flag forms, the integer limits and the switch."""
    line = ["nemik", "--root=/r", "--receipt", "/f", "--no-cluster", "gabion", *LIMITS]
    options = read_options(line)
    assert options.repos == ["nemik", "gabion"]
    assert options.root == Path("/r")
    assert options.receipt == Path("/f")
    assert not options.cluster
    assert (options.max_behind, options.stuck_after) == (3, 9)


def test_help_prints_the_usage_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--help prints usage on stdout and exits 0."""
    with pytest.raises(SystemExit) as raised:
        read_options(["--help"])
    assert raised.value.code == 0
    assert "usage: nemik-pins" in capsys.readouterr().out


def test_a_bad_command_line_exits_two_and_says_why(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """MUTANT: a limit that is not a number must not read as no limit."""
    for line, why in (
        (["--max-behind", "many"], "invalid int value: 'many'"),
        (["--max-behind=--5"], "invalid int value: '--5'"),
        (["--stuck-after=²"], "invalid int value: '²'"),
        (["--stuck-after", "x"], "invalid int value: 'x'"),
        (["--bogus"], "unrecognized argument: --bogus"),
        (["--root"], "--root: expected one argument"),
    ):
        with pytest.raises(SystemExit) as raised:
            read_options(line)
        assert raised.value.code == BAD_USAGE
        assert why in capsys.readouterr().err


def test_every_flag_it_reads_is_in_the_usage_text() -> None:
    """USAGE is hand-written beside VALUED, so a flag added to one and not the other fails."""
    for name in [*VALUED, "--no-cluster"]:
        assert name in USAGE, name
