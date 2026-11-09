# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2077: the wall table agrees with the pinned compiler, one import line to a test.

codon-wall-table.json lists the import lines Codon accepted and refused. A line the table calls
accepted that the compiler refuses hides a wall, and a refused line that compiles overstates one.
The compiler is run once per line, in its own test, so bazel can shard the 120 or so compiles
instead of running them in one process that times out.
"""

import os
from pathlib import Path

import pytest
from codon_walls import compiles, read_table

ROOT = Path(__file__).resolve().parents[1]
CODON = os.environ.get("NEMIK_CODON")
ACCEPTED = "accepted"
REFUSED = "refused"


def _lines() -> list[tuple[str, str]]:
    """Read the table as (import line, what the table says) pairs.

    Returns:
        Every accepted line, then every refused line.

    """
    table = read_table(ROOT)
    return [(line, kind) for kind in (ACCEPTED, REFUSED) for line in table[kind]]


LINES = _lines()


@pytest.mark.skipif(not CODON, reason="the pinned Codon comes from bazel")
@pytest.mark.parametrize(("line", "kind"), LINES, ids=[line for line, _ in LINES])
def test_the_compiler_agrees_with_the_table_on_one_import_line(
    line: str, kind: str
) -> None:
    """An accepted line compiles and a refused line does not."""
    assert compiles(Path(str(CODON)).resolve(), line) == (kind == ACCEPTED)
