# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W818: the shared core's longest chains, over plain data."""

from nemik.core.chains import longest_chains

IDS = ["a", "b", "c", "d", "e", "f"]
# a -> b -> d and a -> c -> d, then d -> e; f stands alone
DEPS = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
DEEP = 4
PAIR = 2


def test_the_longest_chain_and_the_ways_through_each_card() -> None:
    """Four cards deep, with two ways through the diamond; the lone card is not on it."""
    found = longest_chains(IDS, DEPS)
    assert found.length == DEEP
    assert found.paths == {"a": 2, "b": 1, "c": 1, "d": 2, "e": 2}
    assert found.up["e"] == DEEP
    assert found.down["a"] == DEEP
    assert found.up["f"] == found.down["f"] == 1


def test_a_pair_naming_an_unknown_card_or_a_card_with_itself_is_ignored() -> None:
    """Only edges between the given cards count."""
    deps = [("a", "b"), ("a", "zzz"), ("q", "a"), ("b", "b")]
    found = longest_chains(["a", "b"], deps)
    assert found.length == PAIR
    assert found.paths == {"a": 1, "b": 1}


def test_no_cards_is_a_chain_of_nothing() -> None:
    """The empty graph has length zero."""
    found = longest_chains([], [])
    assert found.length == 0
    assert found.paths == {}


def test_a_cycle_is_cut_where_the_walk_meets_itself() -> None:
    """The cycle a, b, c: the visiting order decides the cut, so the answer is stable.

    The up and down walks cut a cycle at different places, so the length is not the cycle's size;
    critical.cycles reports a cycle as a finding of its own.
    """
    deps = [("a", "b"), ("b", "c"), ("c", "a")]
    first = longest_chains(["a", "b", "c"], deps)
    again = longest_chains(["a", "b", "c"], deps)
    assert first.length == again.length
    assert first.paths == again.paths
