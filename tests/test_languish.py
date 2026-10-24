# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W992: a card behind only a grooming umbrella, past the learned bound, languishes."""

from nemik.languish import languishing, learned_bound

GROOMING = ["luthen:W1285"]
TEN = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]


def test_the_bound_is_the_ninetieth_percentile_by_nearest_rank() -> None:
    """Ten values: the 9th smallest. No history, or only zeros: one."""
    assert (learned_bound(TEN), learned_bound([]), learned_bound([0, 0])) == (9, 1, 1)


def test_a_card_waiting_only_on_the_umbrella_past_the_bound_languishes() -> None:
    """Real blocks last up to 6 ticks, so 140 on the umbrella is long and 3 is not."""
    blocked = {
        "luthen:W979": (140, ["luthen:W1285"]),
        "luthen:W990": (3, ["luthen:W1285"]),
        "a:W1": (6, ["b:W2"]),
        "a:W2": (2, ["b:W3"]),
    }
    assert languishing(blocked, GROOMING) == [("luthen:W979", 140, "luthen:W1285")]


def test_a_card_with_another_blocker_does_not_languish() -> None:
    """Waiting on the umbrella and on real work is a real block."""
    blocked = {"luthen:W979": (140, ["luthen:W1285", "luthen:W5"])}
    assert languishing(blocked, GROOMING) == []


def test_the_longest_waiting_come_first() -> None:
    """Ties break by card name."""
    blocked = {
        "x:W2": (50, ["luthen:W1285"]),
        "x:W1": (50, ["luthen:W1285"]),
        "x:W3": (90, ["luthen:W1285"]),
    }
    got = [card for card, _, _ in languishing(blocked, GROOMING)]
    assert got == ["x:W3", "x:W1", "x:W2"]
