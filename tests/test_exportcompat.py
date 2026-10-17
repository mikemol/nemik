# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W635: the derived export withholds exactly what the version-1 list does."""

from pathlib import Path

from nemik.exportcompat import derive, write
from nemik.exportv2 import export_refs

SYMBOLS = ["W1", "W2", "W3"]


def test_the_derived_export_withholds_what_the_v1_list_withholds(
    tmp_path: Path,
) -> None:
    """Through the reader, the refs withheld for the repo equal the v1 refs for the repo."""
    v1 = {"r:W2", "q:W9"}
    path = tmp_path / "r.json"
    write(path, derive("r", SYMBOLS, v1))
    assert export_refs("r", SYMBOLS, path) == {"r:W2"}


def test_an_empty_v1_list_withholds_nothing(tmp_path: Path) -> None:
    """items: [] withholds nothing, as in version 1."""
    path = tmp_path / "r.json"
    write(path, derive("r", SYMBOLS, set()))
    assert export_refs("r", SYMBOLS, path) == set()


def test_another_repos_refs_do_not_leak_into_the_export() -> None:
    """A ref of repo q is not in repo r's withheld list."""
    export = derive("r", SYMBOLS, {"q:W1"})
    assert export["withheld"] == []
