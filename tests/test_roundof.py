# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1024: a round is the top N ready cards, N from landed stacks; drift is outside it."""

from nemik.roundof import (
    CEILING,
    CEILING_TERM,
    capacity,
    drift,
    outside,
    round_of,
    supply,
    width,
)

RANKED = [("W5", "9.0"), ("W2", "4.5"), ("W9", "1.0"), ("W1", "0.0")]
DISJOINT = 3  # a.py, c.py and d.py of the plans below
DISJOINT_BESIDE_C = 2  # with c.py busy: a.py and d.py


def test_supply_counts_the_cards_that_can_stack_without_sharing_a_file() -> None:
    """nemik:W1082: greedy in rank order; no plan never stacks; a busy file blocks its card."""
    plans = [["a.py"], ["a.py", "b.py"], ["c.py"], [], ["d.py"]]
    assert supply(plans, []) == DISJOINT  # the second plan shares a.py
    assert supply(plans, ["c.py"]) == DISJOINT_BESIDE_C
    assert supply([[], []], []) == 0


def test_width_follows_supply_and_names_what_binds() -> None:
    """The landed median never caps it: supply above it wins, the ceiling bounds it."""
    assert width(1, 3, "floor") == (3, "floor")
    assert width(5, 3, "floor") == (5, "supply")
    assert width(CEILING, 3, "floor") == (CEILING, CEILING_TERM)
    assert width(CEILING + 4, 3, "floor") == (CEILING, CEILING_TERM)
    assert width(2, 8, "landings") == (8, "landings")


def test_the_ceiling_says_it_is_declared_not_measured() -> None:
    """nemik:W1092: a label must not claim a measurement the round does not have."""
    assert "declared" in CEILING_TERM
    assert "headroom" not in CEILING_TERM


def test_capacity_is_the_median_stack_size_lifted_to_the_floor() -> None:
    """A median at the floor or above is the landings'; below it, or without stacks, the floor."""
    assert capacity([3, 1, 4]) == (3, "landings")
    assert capacity([4, 9, 6]) == (6, "landings")
    assert capacity([2, 5]) == (3, "floor")
    assert capacity([1, 1, 1]) == (3, "floor")
    assert capacity([]) == (3, "floor")
    assert capacity([0, 0]) == (3, "floor")


def test_the_round_is_the_top_of_the_ranking_with_ranks_from_one() -> None:
    """Three of four, in rank order; a size past the list takes them all; zero takes none."""
    top = [("W5", 1, "9.0"), ("W2", 2, "4.5"), ("W9", 3, "1.0")]
    assert round_of(RANKED, 3) == top
    assert len(round_of(RANKED, 9)) == len(RANKED)
    assert round_of(RANKED, 0) == []


def test_a_card_unblocked_after_the_round_is_fixed_is_not_in_it() -> None:
    """The round is a value: a new ready card changes the next draw, not this one."""
    first = round_of(RANKED, 2)
    later = [("W7", "99.0"), *RANKED]
    assert [symbol for symbol, _, _ in first] == ["W5", "W2"]
    assert [symbol for symbol, _, _ in round_of(later, 2)] == ["W7", "W5"]


def test_drift_counts_the_working_cards_outside_the_round() -> None:
    """Two of three working cards are not in the round."""
    working = ["W5", "W40", "W41"]
    assert outside(working, ["W5", "W2"]) == ["W40", "W41"]
    assert drift(working, ["W5", "W2"]) == (2, 3)
    assert drift([], ["W5"]) == (0, 0)
