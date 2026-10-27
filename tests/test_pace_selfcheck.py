# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1155: a row that reads behind though its own series fell what it owed is named."""

from nemik.pacerun import pace_contradictions
from nemik.pacewrite import contradictions

WINDOW = 10
FELL = [18, 18, 18, 13, 12, 11, 9, 5, 2]
FLAT = [7, 7, 7, 7]
STAMPS = ",".join(str(1000 + n) for n in range(len(FELL)))
EXPORT = (
    '{"metric":{"repo":"r","ratchet":"x.tsv"},"values":'
    f"{FELL},"
    f'"timestamps":[{STAMPS}]}}\n'
)


def test_a_behind_row_whose_series_fell_what_it_owes_is_named() -> None:
    """The planted disagreement: behind with observed 0 though the series fell 16 against 1."""
    series = [("r", "x.tsv", FELL)]
    rows = [("r", "x.tsv", "behind", 0, 1)]
    assert contradictions(series, WINDOW, rows) == [
        "r x.tsv reads behind (owes 1) but fell 16 over its last 8 landings"
    ]


def test_a_behind_row_that_really_fell_short_is_not_named() -> None:
    """A flat series owes one and fell none: behind is right, so nothing to say."""
    assert not contradictions([("r", "x", FLAT)], WINDOW, [("r", "x", "behind", 0, 1)])


def test_an_ok_row_and_a_row_that_owes_nothing_are_left_alone() -> None:
    """The check looks only at behind rows with something owed."""
    series = [("r", "a", FELL), ("r", "b", FELL)]
    rows = [("r", "a", "ok", 16, 1), ("r", "b", "behind", 0, 0)]
    assert not contradictions(series, WINDOW, rows)


def test_the_real_pipeline_agrees_with_itself_on_the_letter_quotes_shape() -> None:
    """After the W1155 fix the verdict reads ok for that series, so the self-check finds nothing."""
    assert not pace_contradictions(EXPORT, "", {})
