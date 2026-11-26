# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1869: nemik-pdf reads its command line with nemik.flags, as argparse read it."""

from pathlib import Path

import pytest

from nemik.pdf import BAD_USAGE, HOST_URL, USAGE, VALUED, read_options


def test_the_view_and_out_are_required_and_the_rest_default() -> None:
    """A view word and --out suffice; the repo and address are empty and the url is the host's."""
    options = read_options(["graph", "--out", "g.pdf"])
    assert options.view == "graph"
    assert options.out == Path("g.pdf")
    assert not options.repo
    assert options.url == HOST_URL
    assert not options.address


def test_every_flag_is_read_in_either_form() -> None:
    """The space and equals forms, with the view word anywhere on the line."""
    options = read_options(
        ["--out=/o", "repo", "--repo", "nemik", "--url", "http://x/", "--address=#/a"]
    )
    assert (options.view, options.repo, options.url, options.address) == (
        "repo",
        "nemik",
        "http://x/",
        "#/a",
    )
    assert options.out == Path("/o")


def test_help_prints_the_usage_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--help prints usage on stdout and exits 0."""
    with pytest.raises(SystemExit) as raised:
        read_options(["--help"])
    assert raised.value.code == 0
    assert "usage: python -m nemik.pdf" in capsys.readouterr().out


def test_a_bad_command_line_exits_two_and_says_why(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """MUTANT: a missing --out or view must not fall through to a render."""
    for line, why in (
        (["graph"], "required: --out"),
        (["--out", "/o"], "required: view"),
        (["a", "b", "--out", "/o"], "unrecognized argument: b"),
        (["a", "--out", "/o", "--bogus"], "unrecognized argument: --bogus"),
        (["a", "--out"], "--out: expected one argument"),
    ):
        with pytest.raises(SystemExit) as raised:
            read_options(line)
        assert raised.value.code == BAD_USAGE
        assert why in capsys.readouterr().err


def test_every_flag_it_reads_is_in_the_usage_text() -> None:
    """USAGE is hand-written beside VALUED, so a flag added to one and not the other fails."""
    for name in VALUED:
        assert name in USAGE, name
