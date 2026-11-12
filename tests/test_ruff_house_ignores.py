# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2125: the house lint's per-file relief is exactly what was reviewed, and no more.

ruff-house.toml's [lint.per-file-ignores] is the one place a rule is relieved for a file, by
responsibility and with a reason, and each entry is a reviewed change. A table can grow one line at
a time in any later stack where only a diff reader would see it, so this pins it to its reviewed
contents: a new entry fails here until the test is edited in the same reviewed change.
"""

import tomllib
from pathlib import Path

from nemik.tomlview import strings, table

HERE = Path(__file__).absolute().parents[1]
REVIEWED = {
    # A test's job is to assert (the house's first relief).
    "tests/test_*.py": ["S101"],
    # Running the ratchet is the whole job of its test: an argv list, no shell, this interpreter.
    "tests/test_ruff_ratchet.py": [
        "suspicious-subprocess-import",
        "subprocess-without-shell-equals-true",
    ],
    # nemik:W2125, github-14 2026-11-10: starting a process through the shell is the sole
    # responsibility of nemik/spawn.py, because the pinned Codon has no subprocess.
    "src/nemik/spawn.py": ["S605"],
}


def test_the_per_file_ignores_are_exactly_the_reviewed_entries() -> None:
    """Hold the table to three entries, each with the rules it was reviewed for."""
    doc: dict[str, object] = tomllib.loads(
        (HERE / "ruff-house.toml").read_text(encoding="utf-8")
    )
    ignores = table(table(doc.get("lint")).get("per-file-ignores"))
    assert {name: strings(rules) for name, rules in ignores.items()} == REVIEWED
