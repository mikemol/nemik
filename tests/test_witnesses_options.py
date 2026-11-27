# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1970: nemik-witnesses reads its flags with nemik.flags, refusing what argparse did."""

import pytest

from nemik.queuefiles import default_root
from nemik.witnesses import BAD_USAGE, main, read_options

DEFAULT_TIMEOUT = "12h"
DEFAULT_EVERY = "30s"
EVERY_FLAG_IN_BOTH_SPELLINGS = [
    "--root=/srv",
    "--apply",
    "--wait",
    "q",
    "--lang=rego",
    "--timeout",
    "1d",
    "--every=5s",
]


def test_the_defaults_are_the_argparse_ones() -> None:
    """With no flags: the fleet root, no wait, no apply, 12h and 30s, and nothing wrong."""
    options = read_options([])
    assert options.errors == []
    assert options.root == default_root()
    assert (options.apply, options.wait, options.lang) == (False, None, "")
    assert (options.timeout, options.every) == (DEFAULT_TIMEOUT, DEFAULT_EVERY)


def test_every_flag_is_read_in_either_spelling() -> None:
    """`--flag value` and `--flag=value` both read, and --apply is a switch."""
    options = read_options(EVERY_FLAG_IN_BOTH_SPELLINGS)
    assert options.errors == []
    assert (str(options.root), options.apply, options.wait) == ("/srv", True, "q")
    assert (options.lang, options.timeout, options.every) == ("rego", "1d", "5s")


def test_a_language_outside_the_choices_is_named() -> None:
    """MUTANT: argparse's choices refused `--lang sql`; the reader names it too."""
    options = read_options(["--wait", "q", "--lang", "sql"])
    assert options.errors == ["argument --lang: invalid choice: 'sql'"]


def test_an_unrecognized_flag_and_a_stray_word_are_named() -> None:
    """A flag nemik-witnesses does not have, and a bare word, are errors."""
    options = read_options(["--nope", "stray"])
    assert any("--nope" in error for error in options.errors)
    assert "unrecognized arguments: stray" in options.errors


def test_a_valued_flag_with_no_value_does_not_eat_the_next_flag() -> None:
    """`--wait --apply` is an error for --wait, and --apply is still read."""
    options = read_options(["--wait", "--apply"])
    assert options.apply is True
    assert options.errors == ["--wait: expected one argument"]


def test_main_exits_with_the_usage_status_on_a_bad_command_line() -> None:
    """The exit status argparse gave for a command line it could not read."""
    with pytest.raises(SystemExit) as raised:
        main(["--lang", "sql"])
    assert raised.value.code == BAD_USAGE
