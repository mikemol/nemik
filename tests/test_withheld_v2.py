# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W634: a repo's own export decides what leaves it, and fails closed per repo."""

import json
from pathlib import Path

from nemik.exportv2 import export_refs

SYMBOLS = ["W1", "W2", "W3"]


def _write(path: Path, doc: dict[str, object]) -> Path:
    """Write an export document.

    Args:
        path: Where to write it.
        doc: The document.

    Returns:
        The path.

    """
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_a_card_the_export_does_not_publish_is_withheld(tmp_path: Path) -> None:
    """Only W1 is in cards: W2 and W3 do not leave the repo."""
    export = _write(
        tmp_path / "x.json",
        {"version": 2, "repo": "r", "cards": [{"symbol": "W1"}], "withheld": []},
    )
    assert export_refs("r", SYMBOLS, export) == {"r:W2", "r:W3"}


def test_a_named_withheld_ref_is_withheld_even_if_listed(tmp_path: Path) -> None:
    """A ref in `withheld` stays withheld whatever else says."""
    export = _write(
        tmp_path / "x.json",
        {
            "version": 2,
            "repo": "r",
            "cards": [{"symbol": s} for s in SYMBOLS],
            "withheld": ["r:W2"],
        },
    )
    assert export_refs("r", SYMBOLS, export) == {"r:W2"}


def test_no_export_publishes_nothing_of_the_repo(tmp_path: Path) -> None:
    """Fail closed: a missing export withholds every card."""
    assert export_refs("r", SYMBOLS, tmp_path / "none.json") == {
        "r:W1",
        "r:W2",
        "r:W3",
    }


def test_an_export_that_does_not_parse_or_is_another_repos_fails_closed(
    tmp_path: Path,
) -> None:
    """Not JSON, an unknown version and another repo's export each withhold everything."""
    everything = {f"r:{s}" for s in SYMBOLS}
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert export_refs("r", SYMBOLS, bad) == everything
    old = _write(tmp_path / "old.json", {"version": 1, "items": []})
    assert export_refs("r", SYMBOLS, old) == everything
    other = _write(
        tmp_path / "other.json",
        {"version": 2, "repo": "q", "cards": [{"symbol": "W1"}], "withheld": []},
    )
    assert export_refs("r", SYMBOLS, other) == everything
