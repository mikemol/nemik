# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1936: nemik-static reads its flags with nemik.flags and refuses what argparse refused."""

import pytest

from nemik.staticserve import BAD_USAGE, DEFAULT_BIND, DEFAULT_PORT, main, read_options


def test_the_defaults_are_the_argparse_ones() -> None:
    """Only --root is given: bind is 127.0.0.1 and the port 8750, with nothing wrong."""
    options = read_options(["--root", "/srv"])
    assert options.errors == []
    assert str(options.root) == "/srv"
    assert (options.bind, options.port) == (DEFAULT_BIND, DEFAULT_PORT)
    assert (DEFAULT_BIND, DEFAULT_PORT) == ("127.0.0.1", 8750)


def test_every_flag_is_read_in_either_spelling() -> None:
    """`--flag value` and `--flag=value` both read."""
    options = read_options(["--root=/srv", "--bind", "10.1.2.3", "--port=9000"])
    assert options.errors == []
    assert (str(options.root), options.bind, options.port) == ("/srv", "10.1.2.3", 9000)


def test_a_missing_root_is_named() -> None:
    """MUTANT: argparse required --root; a command line without it is refused, not defaulted."""
    options = read_options([])
    assert options.errors == ["the following arguments are required: --root"]


def test_a_port_that_is_not_a_whole_number_is_named_and_reads_as_the_default() -> None:
    """Argparse refused `--port abc`; the reader names it and keeps the answer a number."""
    options = read_options(["--root", "/srv", "--port", "abc"])
    assert options.errors == ["argument --port: invalid int value: 'abc'"]
    assert options.port == DEFAULT_PORT


def test_an_unrecognized_flag_and_a_stray_word_are_named() -> None:
    """A flag nemik-static does not have, and a bare word, are errors."""
    options = read_options(["--root", "/srv", "--nope", "stray"])
    assert "unrecognized argument: --nope" in options.errors
    assert "unrecognized arguments: stray" in options.errors


def test_main_exits_with_the_usage_status_on_a_bad_command_line() -> None:
    """The exit status argparse gave for a command line it could not read."""
    with pytest.raises(SystemExit) as raised:
        main(["--port", "9000"])
    assert raised.value.code == BAD_USAGE
