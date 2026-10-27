# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W730: which modules of the installed nemik differ from the source tree.

A profile or tool that imports the venv's nemik runs whatever was installed, not the tree beside
it. Comparing each src/nemik module's text with the installed copy's names the stale ones, so old
code cannot run silently. Plain strings and pathlib only, so it compiles under Codon.
"""

from pathlib import Path


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
