# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2044: where nemik.flags differs from argparse, and what its callers' usage texts say."""

import argparse

import pytest

from nemik import metrics, mspdi
from nemik.flags import parse_flags

VALUED = ["--root", "--family"]
SWITCHES = ["--verbose"]


def test_a_forgotten_value_does_not_eat_the_next_flag() -> None:
    """MUTANT: taking --family as --root's value runs the CLI on the wrong root."""
    line = ["--root", "--family", "a"]
    ap = argparse.ArgumentParser(exit_on_error=False)
    ap.add_argument("--root")
    ap.add_argument("--family")
    with pytest.raises(argparse.ArgumentError, match="expected one argument"):
        ap.parse_args(line)
    flags = parse_flags(line, VALUED, SWITCHES)
    assert flags.errors == ["--root: expected one argument"]
    assert flags.every("--root") == []
    assert flags.every("--family") == ["a"]


def test_a_flag_last_on_the_line_has_no_value() -> None:
    """The same error at the end of the line, and a following switch is not a value either."""
    assert parse_flags(["--root"], VALUED, SWITCHES).errors == [
        "--root: expected one argument"
    ]
    again = parse_flags(["--root", "--verbose"], VALUED, SWITCHES)
    assert again.errors == ["--root: expected one argument"]
    assert again.has("--verbose")


def test_an_abbreviation_and_a_bare_double_dash_are_refused() -> None:
    """Deliberate differences from argparse, which takes both (see the module docstring)."""
    flags = parse_flags(["--fam", "a", "--"], VALUED, SWITCHES)
    assert flags.errors == [
        "unrecognized argument: --fam",
        "unrecognized argument: --",
    ]
    assert flags.rest == ["a"]


def test_every_flag_a_cli_reads_is_in_its_usage_text() -> None:
    """USAGE is written beside VALUED by hand, so a flag added to one and not the other fails."""
    for name in metrics.VALUED:
        assert name in metrics.USAGE, name
    for name in mspdi.VALUED:
        assert name in mspdi.USAGE, name
