# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W613: the stackable pick is greedy in rank order over exact files."""

from nemik.stackable import pick


def test_a_card_that_shares_a_file_with_a_higher_ranked_one_waits() -> None:
    """W2 overlaps W1 on b.py and waits; W3 is disjoint from both and joins."""
    cards = ["n:W1", "n:W2", "n:W3"]
    files = [["a.py", "b.py"], ["b.py"], ["c.py"]]
    assert pick(cards, files, []) == ["n:W1", "n:W3"]


def test_a_file_in_flight_blocks_the_card_that_touches_it() -> None:
    """A file already staged is not available to the next stack."""
    assert pick(["n:W1", "n:W2"], [["a.py"], ["b.py"]], ["a.py"]) == ["n:W2"]


def test_a_card_with_no_manifest_never_stacks() -> None:
    """An unplanned card cannot be shown disjoint, so it is left out."""
    assert pick(["n:W1", "n:W2"], [[], ["b.py"]], []) == ["n:W2"]


def test_the_pick_is_greedy_not_maximum() -> None:
    """W1 spans two files that W2 and W3 hold alone: greedy keeps W1 though W2 and W3 make two."""
    cards = ["n:W1", "n:W2", "n:W3"]
    assert pick(cards, [["a.py", "b.py"], ["a.py"], ["b.py"]], []) == ["n:W1"]
