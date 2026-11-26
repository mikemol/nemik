# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2044: the Codon-compatible flag reader reads what argparse read, and names the rest."""

import argparse

from nemik.flags import parse_flags

VALUED = ["--root", "--family", "--runs"]
SWITCHES = ["--verbose"]


class _Reference(argparse.Namespace):
    """The parsed line as argparse reads it, each attribute typed."""

    root: str | None
    runs: str | None
    family: list[str] | None
    verbose: bool
    words: list[str]


def _reference(argv: list[str]) -> _Reference:
    """Parse a line with argparse, the reference this reader is held to.

    Returns:
        What argparse made of the line.

    """
    ap = argparse.ArgumentParser(exit_on_error=False)
    ap.add_argument("--root")
    ap.add_argument("--runs")
    ap.add_argument("--family", action="append")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("words", nargs="*")
    return ap.parse_args(argv, namespace=_Reference())


def test_it_reads_what_argparse_read() -> None:
    """A spread of lines: space and equals forms, repeats, a switch, positionals."""
    lines = [
        [],
        ["--root", "/x"],
        ["--root=/x", "--runs", "r"],
        ["--family", "a", "--family=b", "--family", "c"],
        ["--verbose", "word", "--root", "/y"],
        ["--root", "/a", "--root", "/b"],
        ["--runs=a=b"],
    ]
    for line in lines:
        flags = parse_flags(line, VALUED, SWITCHES)
        expected = _reference(line)
        assert not flags.errors, line
        assert flags.first("--root", "") == (expected.root or ""), line
        assert flags.first("--runs", "") == (expected.runs or ""), line
        assert flags.every("--family") == (expected.family or []), line
        assert flags.has("--verbose") == expected.verbose, line
        assert flags.rest == expected.words, line


def test_the_last_value_of_a_repeated_flag_wins() -> None:
    """Argparse keeps the last --root, and so does first()."""
    flags = parse_flags(["--root", "/a", "--root", "/b"], VALUED, SWITCHES)
    assert flags.first("--root", "none") == "/b"
    assert flags.every("--root") == ["/a", "/b"]


def test_a_flag_not_given_reads_its_default() -> None:
    """Absent flags answer the default, an empty list and False."""
    flags = parse_flags([], VALUED, SWITCHES)
    assert flags.first("--root", "d") == "d"
    assert flags.every("--family") == []
    assert not flags.has("--verbose")


def test_an_unknown_flag_is_named_never_dropped() -> None:
    """MUTANT: swallowing --bad as a positional would run the CLI on a typo."""
    flags = parse_flags(["--bad", "--root", "/x"], VALUED, SWITCHES)
    assert flags.errors == ["unrecognized argument: --bad"]
    assert flags.first("--root", "") == "/x"
    assert flags.rest == []


def test_a_valued_flag_at_the_end_has_no_value() -> None:
    """The error names the flag; nothing is read past the end of the line."""
    flags = parse_flags(["--root"], VALUED, SWITCHES)
    assert flags.errors == ["--root: expected one argument"]
    assert flags.every("--root") == []


def test_a_switch_with_a_value_is_an_error() -> None:
    """A switch given a value, as in --verbose=1, is named."""
    flags = parse_flags(["--verbose=1"], VALUED, SWITCHES)
    assert flags.errors == ["--verbose: takes no argument"]
    assert not flags.has("--verbose")


def test_an_equals_inside_a_positional_stays_a_word() -> None:
    """Only a word that starts with the dashes is split at its equals sign."""
    flags = parse_flags(["a=b"], VALUED, SWITCHES)
    assert flags.rest == ["a=b"]
    assert not flags.errors
