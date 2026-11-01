# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1384: the one place a command writes its output, so a CLI's contract is not a bare print.

A command's stdout is its interface (a JSON document, a table, a list of argv lines), so it is
written on purpose, through these three functions, not through `print` scattered over the source.
Pure and stdlib only, with no boolean or keyword-only parameter (the pinned Codon cannot parse a
bare star), so the Codon census can compile it.
"""

import sys


def say(text: str = "") -> None:
    """Write a line to stdout."""
    sys.stdout.write(text + "\n")


def say_raw(text: str) -> None:
    """Write text to stdout as given, with no newline added."""
    sys.stdout.write(text)


def warn(text: str) -> None:
    """Write a line to stderr."""
    sys.stderr.write(text + "\n")
