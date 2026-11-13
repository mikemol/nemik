# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2164: nemik-ask reads its command line by hand and agrees with the argparse it replaced.

nemik.ask_cli used argparse, a Codon wall (the second of the two its leaves failed on). The frozen
parser below is the old one, unchanged in what it accepts; every accepted line must give the same
options through nemik.ask_cli.parse and every rejected line the same exit status. Where the hand
parser differs on purpose (the usage text, which names no abbreviations) a test says so.
"""

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from nemik.ask_cli import DEFAULT_FLOOR, USAGE, parse

if TYPE_CHECKING:
    from collections.abc import Callable

BASE = ["--filer", "life", "--to", "mtools", "--slug", "ask-x", "--claim", "x is wrong"]
USAGE_ERROR = 2
Fields = tuple[str, str, str, str, str, str, str, bool]


def _frozen(argv: list[str]) -> Fields:
    """Parse as nemik.ask_cli did before W2164: argparse, frozen.

    Returns:
        The eight option values, paths as strings.

    """
    ap = argparse.ArgumentParser(prog="nemik-ask")
    ap.add_argument("--filer", required=True)
    ap.add_argument("--to", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--claim", required=True)
    ap.add_argument("--owner-card", default="")
    ap.add_argument("--state", type=Path, default=Path(".claude/paths-forward.json"))
    ap.add_argument("--floor", type=Path, default=DEFAULT_FLOOR)
    ap.add_argument("--apply", action="store_true")
    ns = ap.parse_args(argv)
    filer: str = ns.filer
    owner: str = ns.to
    slug: str = ns.slug
    claim: str = ns.claim
    owner_card: str = ns.owner_card
    state: Path = ns.state
    floor: Path = ns.floor
    apply: bool = ns.apply
    return (filer, owner, slug, claim, owner_card, str(state), str(floor), apply)


def _ours(argv: list[str]) -> Fields:
    """Parse with the hand parser.

    Returns:
        The eight option values, paths as strings.

    """
    out = parse(argv)
    return (
        out.filer,
        out.to,
        out.slug,
        out.claim,
        out.owner_card,
        str(out.state),
        str(out.floor),
        out.apply,
    )


def _exit_status(parser: Callable[[list[str]], Fields], argv: list[str]) -> int:
    """Run a parser over `argv` and give its SystemExit status.

    Returns:
        The exit status the parser stopped with.

    """
    with pytest.raises(SystemExit) as stopped:
        parser(argv)
    code = stopped.value.code
    assert isinstance(code, int)
    return code


ACCEPTED = [
    BASE,
    [*BASE, "--apply"],
    [*BASE, "--owner-card", "W12"],
    ["--filer=life", "--to=mtools", "--slug=ask-x", "--claim=x is wrong"],
    ["--fil", "life", "--t", "mtools", "--sl", "ask-x", "--cl", "x is wrong"],
    [*BASE, "--st", "q.json", "--flo", "floor", "--ap", "--ow", "W3"],
    [*BASE, "--claim=", "--owner-card="],
    ["--filer", "-", "--to", "mtools", "--slug", "s", "--claim", "-"],
]
REJECTED = [
    [*BASE, "--"],
    [],
    BASE[:-2],
    [*BASE, "extra"],
    [*BASE, "--nope"],
    [*BASE, "--s", "x"],
    [*BASE, "--apply=1"],
    ["--filer"],
    [*BASE, "--state"],
    [*BASE, "--", "after"],
]


@pytest.mark.parametrize("argv", ACCEPTED)
def test_every_accepted_line_gives_the_options_argparse_gave(argv: list[str]) -> None:
    """Agree with the frozen argparse parser on every accepted command line."""
    assert _ours(argv) == _frozen(argv)


@pytest.mark.parametrize("argv", REJECTED)
def test_every_rejected_line_stops_with_the_status_argparse_gave(argv: list[str]) -> None:
    """Stop with a usage error, as the frozen argparse parser does."""
    assert _exit_status(_ours, argv) == _exit_status(_frozen, argv) == USAGE_ERROR


def test_help_prints_the_usage_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """Print the usage on stdout and stop with 0 for -h and --help."""
    for flag in ("-h", "--help"):
        assert _exit_status(_ours, [flag]) == 0
        assert capsys.readouterr().out == f"{USAGE}\n"


def test_a_missing_option_is_named_with_the_usage(capsys: pytest.CaptureFixture[str]) -> None:
    """Name every missing required option, after the usage, on stderr."""
    assert _exit_status(_ours, ["--filer", "life"]) == USAGE_ERROR
    said = capsys.readouterr().err
    assert said.startswith(USAGE)
    assert "the following arguments are required: --to, --slug, --claim" in said


def test_an_unknown_argument_and_an_ambiguous_prefix_are_named(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Report the argument that is not recognised, whether unknown or an ambiguous prefix."""
    assert _exit_status(_ours, [*BASE, "--nope"]) == USAGE_ERROR
    assert "unrecognized arguments: --nope" in capsys.readouterr().err
    assert _exit_status(_ours, [*BASE, "--s", "x"]) == USAGE_ERROR
    assert "unrecognized arguments: --s" in capsys.readouterr().err
