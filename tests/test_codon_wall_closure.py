# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2103: the import closure of tools/codon_walls.py bounds itself, not the clock.

A cycle test whose mutant (the visited set removed) loops forever was killed only by bazel's 30 s
wall-clock timeout, which this fleet does not rely on. Here `targets`, called once per reference a
module makes, is wrapped to count its calls and to fail the test at the call past the number of
references in the package, so the mutant is a named failure at once.
"""

from pathlib import Path

import codon_walls
import pytest
from codon_walls import Ref, closure, read_package

CYCLE = {
    "a.py": "from nemik import b\n",
    "b.py": "from nemik import c\n",
    "c.py": "from nemik import a\n",
}
LEAF = {"d.py": "import json\n"}


def _package(tmp: Path, files: dict[str, str]) -> dict[str, codon_walls.Facts]:
    pkg = tmp / "src" / "nemik"
    pkg.mkdir(parents=True)
    for name, text in files.items():
        (pkg / name).write_text(text, encoding="utf-8")
    return read_package(tmp / "src")


def _count_targets(monkeypatch: pytest.MonkeyPatch, limit: int) -> list[Ref]:
    # wrap `targets` so a call past `limit` fails the test, and hand back the refs it saw
    seen: list[Ref] = []
    real = codon_walls.targets

    def counted(ref: Ref, known: set[str]) -> set[str]:
        seen.append(ref)
        if len(seen) > limit:
            pytest.fail(
                f"targets called {len(seen)} times for {limit} references: unbounded"
            )
        return real(ref, known)

    monkeypatch.setattr(codon_walls, "targets", counted)
    return seen


def test_a_cycle_resolves_each_reference_once_and_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Three modules in a ring make three references: the closure of any is all three, in three."""
    package = _package(tmp_path, CYCLE)
    seen = _count_targets(monkeypatch, len(CYCLE))
    assert closure("a", package) == ["a", "b", "c"]
    assert len(seen) == len(CYCLE)


def test_a_module_outside_the_ring_adds_no_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolution follows the imports: a leaf nothing in the ring imports costs nothing."""
    package = _package(tmp_path, {**CYCLE, **LEAF})
    seen = _count_targets(monkeypatch, len(CYCLE))
    assert closure("a", package) == ["a", "b", "c"]
    assert len(seen) == len(CYCLE)
