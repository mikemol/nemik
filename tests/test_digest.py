# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W641: repeated Info rows collapse to one counted line; everything else stays."""

from nemik.digest import Row, collapse

NO_MANIFEST = "ready leaf with no manifest of planned changes"


def test_info_rows_that_share_a_message_become_one_counted_row() -> None:
    """Three cards with the same Info message print once, with the count."""
    rows: list[Row] = [("Info", f"W{n}", NO_MANIFEST) for n in (1, 2, 3)]
    assert collapse(rows) == [("Info", "--", f"3 cards: {NO_MANIFEST}")]


def test_warnings_and_violations_stay_in_full() -> None:
    """A Warning shared by two cards is not collapsed: only Info is."""
    rows: list[Row] = [
        ("Warning", "W1", "same"),
        ("Warning", "W2", "same"),
        ("Violation", "W3", "bad"),
    ]
    assert collapse(rows) == rows


def test_an_info_message_on_one_card_is_kept_whole() -> None:
    """One card is one line already: it keeps its symbol."""
    rows: list[Row] = [("Info", "W9", "only here")]
    assert collapse(rows) == rows


def test_the_counted_row_sits_where_the_first_one_was() -> None:
    """Order is kept: the collapsed row replaces the first, later copies vanish."""
    rows: list[Row] = [
        ("Warning", "W1", "w"),
        ("Info", "W2", "i"),
        ("Warning", "W3", "w2"),
        ("Info", "W4", "i"),
    ]
    assert collapse(rows) == [
        ("Warning", "W1", "w"),
        ("Info", "--", "2 cards: i"),
        ("Warning", "W3", "w2"),
    ]
