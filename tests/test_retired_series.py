# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1040: a tombstoned ratchet leaves the pace, a silent one stays unknown."""

from nemik.pacerun import pace_document_floored, retired_of

ENDED = (
    '{"metric":{"repo":"r","ratchet":"x.json","guessed":"false"},'
    '"values":[3,3],"timestamps":[1000,2000]}\n'
)
GOING = (
    '{"metric":{"repo":"r","ratchet":"y.json","guessed":"false"},'
    '"values":[2,2,2,2],"timestamps":[1000,2000,300000,400000]}\n'
)
LISTED = (
    '{"metric":{"repo":"r","ratchet":"x.json","reason":"paid-to-zero-and-removed"},'
    '"values":[1,1],"timestamps":[300000,400000]}\n'
)
LAPSED = LISTED.replace("[1,1]", "[1,0]")
STAMP = "2026-10-27T02:00:00Z"
KEY = "r\nx.json"


def test_a_tombstone_names_the_ratchet_while_its_newest_sample_is_set() -> None:
    """The store lists a tombstone as 1 on every run; a sample of 0 is no tombstone."""
    assert retired_of(LISTED) == frozenset({KEY})
    assert retired_of(LAPSED) == frozenset()
    assert retired_of("") == frozenset()


def test_an_ended_series_with_a_tombstone_leaves_the_pace() -> None:
    """The ratchet that ended and is listed retired has no row; the one still written keeps its."""
    text = pace_document_floored(ENDED + GOING, "", STAMP, {}, retired_of(LISTED))
    assert "x.json" not in text
    assert "y.json" in text


def test_an_ended_series_without_a_tombstone_stays_unknown() -> None:
    """Silence alone is not a retirement: the row stays, and reads unknown."""
    text = pace_document_floored(ENDED + GOING, "", STAMP, {})
    assert "x.json" in text
    assert "unknown" in text


def test_a_tombstone_does_not_drop_a_series_that_is_still_written() -> None:
    """A path that reappears after its tombstone is a new ratchet, judged again."""
    text = pace_document_floored(GOING, "", STAMP, {}, frozenset({"r\ny.json"}))
    assert "y.json" in text
