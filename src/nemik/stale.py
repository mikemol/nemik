# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W730: which modules of the installed nemik differ from the source tree.

A profile or tool that imports the venv's nemik runs whatever was installed, not the tree beside
it. Comparing each src/nemik module's text with the installed copy's names the stale ones, so old
code cannot run silently. Plain strings and pathlib only, so it compiles under Codon.

`nemik-stale SOURCE_DIR INSTALLED_DIR` prints one line per stale module and exits 1 when any is
stale, 0 when the install matches the tree, 2 for a wrong command line or a missing directory.
"""

import sys
from pathlib import Path

STALE_EXIT = 1
USAGE_EXIT = 2
ARGUMENTS = 2  # the source directory and the installed one


def stale_modules(source_dir: Path, installed_dir: Path) -> list[str]:
    """Name the modules whose installed copy is missing or differs from the source tree's.

    Args:
        source_dir: The tree's src/nemik directory.
        installed_dir: The installed nemik package directory.

    Returns:
        The stale module file names, sorted; empty when the install matches the tree.

    """
    stale: list[str] = []
    for source in sorted(source_dir.glob("*.py")):
        installed = installed_dir / source.name
        if not installed.is_file() or installed.read_text(
            encoding="utf-8"
        ) != source.read_text(encoding="utf-8"):
            stale.append(source.name)
    return stale


def check(words: list[str]) -> int:
    """Run the check over a command line and print what is stale.

    Args:
        words: The arguments after the program name: the source directory, then the installed one.

    Returns:
        0 when the install matches the tree, STALE_EXIT when a module is stale, USAGE_EXIT for
        other than two arguments or a directory that does not exist.

    """
    if len(words) != ARGUMENTS:
        sys.stdout.write("usage: nemik-stale SOURCE_DIR INSTALLED_DIR\n")
        return USAGE_EXIT
    source_dir = Path(words[0])
    installed_dir = Path(words[1])
    for directory in (source_dir, installed_dir):
        if not directory.is_dir():
            sys.stdout.write(f"not a directory: {directory}\n")
            return USAGE_EXIT
    stale = stale_modules(source_dir, installed_dir)
    for name in stale:
        sys.stdout.write(f"STALE {name}\n")
    return STALE_EXIT if stale else 0


def main() -> int:
    """Run the check over the process's own command line.

    Returns:
        check's exit code over the arguments the process was started with.

    """
    return check(sys.argv[1:])
