# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2077: closure_evidence hashes a module's closure, as evidence for a rebaseline entry.

A table growth that raises codon-walls.json is a declared rise (rebaselines.json). The entry cites
the closure evidence of the modules it moved: a module's hash changes when any module it reaches
changes, and does not change when a module it does not reach does.
"""

from pathlib import Path

import codon_walls

FILES = {"a.py": "X = 1\n", "b.py": "from nemik import a\n", "c.py": "Y = 1\n"}


def _package(root: Path) -> Path:
    """Write the small package under root/src/nemik.

    Args:
        root: The repository root.

    Returns:
        The package directory.

    """
    pkg = root / "src" / "nemik"
    pkg.mkdir(parents=True)
    for name, text in FILES.items():
        (pkg / name).write_text(text, encoding="utf-8")
    return pkg


def _evidence(root: Path) -> dict[str, str]:
    return codon_walls.closure_evidence(codon_walls.read_package(root / "src"))


def _change_a(pkg: Path) -> None:
    (pkg / "a.py").write_text("import hashlib\n", encoding="utf-8")


def test_a_change_in_the_closure_changes_the_hash(tmp_path: Path) -> None:
    """Module b imports a, so a change in a moves b's hash and a's own."""
    pkg = _package(tmp_path)
    before = _evidence(tmp_path)
    _change_a(pkg)
    after = _evidence(tmp_path)
    assert after["a"] != before["a"]
    assert after["b"] != before["b"]


def test_a_change_outside_the_closure_leaves_the_hash(tmp_path: Path) -> None:
    """Module c does not reach a, so a change in a does not move c's hash."""
    pkg = _package(tmp_path)
    before = _evidence(tmp_path)
    _change_a(pkg)
    assert _evidence(tmp_path)["c"] == before["c"]


def test_the_hash_is_stable_for_the_same_text(tmp_path: Path) -> None:
    """Measuring twice gives the same digests."""
    _package(tmp_path)
    assert _evidence(tmp_path) == _evidence(tmp_path)
