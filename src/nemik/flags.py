# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2044: one typed command-line flag reader that compiles under Codon, in place of argparse.

argparse is a Codon wall for every CLI shell (`docs/codon-walls.md`), and moving a shell into a new
`*_cli` module only moves the wall into a new failing row. This reads the shapes nemik's CLIs use:
`--name value`, `--name=value`, a repeated valued flag, a switch with no value, and positional
words. A flag it was not told about, and a valued flag with no value after it, are named in
`errors` and never dropped: the caller prints them and exits 2, as argparse did. A value that is
itself a `--flag` is not taken as the value (`--root --repo a` is "--root: expected one
argument"). Two differences from argparse are deliberate: a bare `--` is unrecognized (argparse
ends option parsing there), and an abbreviation (`--rep` for `--repo`) is refused where argparse
accepts it, so a caller that took abbreviations must spell the flag out. It is a plain
class and plain loops, which the pinned Codon compiles (probed 2026-11-25, `sys.argv` through the
reader). Typed conversion (a Path, an int) stays with the caller, one `Flags.first` away.
"""

import sys

PREFIX = "--"
SEPARATOR = "="


def command_line() -> list[str]:
    """Read the process's own command line.

    Returns:
        The words after the program name.

    """
    return sys.argv[1:]


class Flags:
    """What one command line said."""

    values: dict[str, list[str]]
    switches: list[str]
    rest: list[str]
    errors: list[str]

    def __init__(
        self,
        values: dict[str, list[str]],
        switches: list[str],
        rest: list[str],
        errors: list[str],
    ) -> None:
        """Hold the four parts of a parsed command line."""
        self.values = values
        self.switches = switches
        self.rest = rest
        self.errors = errors

    def first(self, name: str, default: str) -> str:
        """Read one valued flag.

        Returns:
            The last value given for name (argparse keeps the last), else default.

        """
        given = self.values.get(name, [])
        return given[-1] if given else default

    def every(self, name: str) -> list[str]:
        """Read a repeatable valued flag.

        Returns:
            Every value given for name, in order; empty when it was not given.

        """
        return self.values.get(name, [])

    def has(self, name: str) -> bool:
        """Say whether a switch was given.

        Returns:
            True when the switch name appeared.

        """
        return name in self.switches


def _split(word: str) -> tuple[str, str, bool]:
    """Split `--name=value` at its first equals sign.

    Returns:
        (name, value, whether a value was attached); a word with no equals sign is all name.

    """
    at = word.find(SEPARATOR)
    if word.startswith(PREFIX) and at >= 0:
        return word[:at], word[at + 1 :], True
    return word, "", False


def parse_flags(argv: list[str], valued: list[str], switches: list[str]) -> Flags:
    """Read a command line against the flags a CLI declares.

    Args:
        argv: The words after the program name.
        valued: The flags that take one value, each spelled with its dashes.
        switches: The flags that take none.

    Returns:
        The values by flag, the switches given, the positional words and the errors.

    """
    values: dict[str, list[str]] = {}
    given: list[str] = []
    rest: list[str] = []
    errors: list[str] = []
    i = 0
    while i < len(argv):
        name, value, attached = _split(argv[i])
        if name in valued:
            if not attached:
                if i + 1 >= len(argv) or argv[i + 1].startswith(PREFIX):
                    # a forgotten value must not eat the next flag (argparse refuses it too)
                    errors.append(f"{name}: expected one argument")
                    i += 1
                    continue
                i += 1
                value = argv[i]
            values.setdefault(name, []).append(value)
        elif name in switches:
            if attached:
                errors.append(f"{name}: takes no argument")
            else:
                given.append(name)
        elif name.startswith(PREFIX):
            errors.append(f"unrecognized argument: {name}")
        else:
            rest.append(argv[i])
        i += 1
    return Flags(values, given, rest, errors)
