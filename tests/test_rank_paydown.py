# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W993: a repo behind a ratchet's required fall ranks that ratchet's paydown cards first."""

from pathlib import Path

import pytest

from nemik import pacecli
from nemik.pacecli import behind_files
from nemik.score import load_bands, tagged_band

HEAD = '{"as_of": "2026-10-26T09:34:35Z", "window": "10"}\n'
BEHIND_ROW = (
    '{"repo": "nemik", "ratchet": "codon-baseline.json", "state": "behind", '
    '"observed": "0", "required": "1"}\n'
)
OK_ROW = (
    '{"repo": "nemik", "ratchet": "ruff-baseline.json", "state": "ok", '
    '"observed": "5", "required": "2"}\n'
)
OTHER_ROW = (
    '{"repo": "mtools", "ratchet": "x.json", "state": "behind", '
    '"observed": "0", "required": "1"}\n'
)
CODON = "file:codon-baseline.json"
WHY = "pays down file:codon-baseline.json, which is behind"
PLAIN = ("normal", "unscored")


def test_a_paydown_card_of_a_behind_ratchet_takes_the_velocity_band() -> None:
    """The card is tagged with the ratchet's file; a behind repo ranks it with velocity."""
    bands = load_bands()
    got = tagged_band("normal", "unscored", {CODON, "docs"}, frozenset({CODON}))
    assert got == ("velocity", WHY)
    assert bands.rank("velocity") < bands.rank("critical")


def test_a_write_mark_on_the_tag_does_not_hide_it() -> None:
    """A card that edits the ratchet file carries it as file:<path>!w; it is the same file."""
    got = tagged_band("normal", "unscored", {CODON + "!w"}, frozenset({CODON}))
    assert got == ("velocity", WHY)


def test_the_same_card_is_not_lifted_when_its_ratchet_is_not_behind() -> None:
    """An ok repo's paydown card ranks by its vector, like any other card."""
    assert tagged_band("normal", "unscored", {CODON}, frozenset()) == PLAIN
    assert tagged_band("normal", "unscored", {"docs"}, frozenset({CODON})) == PLAIN


def test_velocity_still_wins_over_the_paydown_reason() -> None:
    """A card tagged velocity keeps the reason the owner gave."""
    got = tagged_band("normal", "unscored", {"velocity", CODON}, frozenset({CODON}))
    assert got == ("velocity", "touches velocity")


def test_the_behind_files_are_the_repos_own_behind_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a behind row of the repo asked about counts: not ok rows, not another repo's."""
    monkeypatch.setattr(pacecli, "EXPORT_TREE", tmp_path)
    (tmp_path / "ratchet-pace.json").write_text(
        HEAD + BEHIND_ROW + OK_ROW + OTHER_ROW, encoding="utf-8"
    )
    assert behind_files("nemik") == [CODON]
    assert behind_files("mtools") == ["file:x.json"]
    assert behind_files("gabion") == []


def test_a_dark_pace_file_reorders_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing or unreadable, the pace names no behind file; the loud signals are elsewhere."""
    monkeypatch.setattr(pacecli, "EXPORT_TREE", tmp_path)
    assert behind_files("nemik") == []
    (tmp_path / "ratchet-pace.json").write_text("not a pace file\n", encoding="utf-8")
    assert behind_files("nemik") == []
