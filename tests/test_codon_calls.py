# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: every registered call prints the same under CPython and the pinned Codon.

The census compiles `import nemik.<module>` only, so it cannot see a module that compiles alone and
fails when called. fixtures/apischema/codon-calls.txt lists calls (module|call|expected) and
tools/codon_call.py runs each one three ways. A line marked DIFF is a negative control that must
differ, which is what makes an OK on the other lines mean something.
"""

import os
from pathlib import Path

import pytest
from codon_call import verdicts

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "tests" / "fixtures" / "apischema" / "codon-calls.txt"
_STAGED = os.environ.get("NEMIK_CODON")
if not _STAGED:
    pytest.skip(
        "the pinned Codon comes from bazel (MODULE.bazel @codon, W566)",
        allow_module_level=True,
    )
CODON = Path(_STAGED).resolve()
LINES = [
    line
    for line in REGISTRY.read_text(encoding="utf-8").splitlines()
    if line and not line.startswith("#")
]


@pytest.mark.parametrize("line", LINES)
def test_a_registered_call_prints_the_same_in_both_modes(line: str) -> None:
    """OK in both modes for a call, DIFF in both for the negative control."""
    module, expr, expected = line.split("|", 2)
    want = None if expected in {"-", "DIFF"} else expected
    results = verdicts(CODON, ROOT / "src", module, expr, want)
    marker = "DIFF" if expected == "DIFF" else "OK"
    assert [r.split()[0] for r in results] == [marker, marker], results


def test_the_registry_holds_a_negative_control() -> None:
    """At least one line expects DIFF, so the check is known to be able to fail."""
    assert any(line.endswith("|DIFF") for line in LINES)
