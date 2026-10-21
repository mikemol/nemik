# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W826: the treemap model's forest over plain data."""

from nemik.core.treemap import ENABLES, NONE, WAITS, forest_of, tree_of

# a=0 b=1 c=2 d=3 e=4 f=5: a enables b and c, both enable d, d enables e; f stands alone
DIAMOND = [
    (0, 1, ENABLES),
    (0, 2, ENABLES),
    (1, 3, ENABLES),
    (2, 3, ENABLES),
    (3, 4, ENABLES),
]
ALL_OPEN = [True] * 6
SIX = 6
D = 3


def test_each_card_goes_under_the_heaviest_thing_it_enables() -> None:
    """Card a enables b and c, equally deep: the lower wins; the other stays a drawn edge."""
    tree = tree_of(SIX, ALL_OPEN, DIAMOND)
    assert tree.parent == [1, 3, 3, 4, NONE, NONE]
    assert tree.kids[D] == [1, 2]
    assert tree.roots == [4, 5]


def test_own_weight_counts_the_downstream_and_weight_adds_the_kids() -> None:
    """The own weight is 1 plus the open cards it reaches; the weight adds the forest beneath."""
    tree = tree_of(SIX, ALL_OPEN, DIAMOND)
    assert tree.own == [5, 3, 3, 2, 1, 1]
    assert tree.weight == [5, 8, 3, 13, 14, 1]


def test_waits_count_toward_own_weight_but_not_toward_the_forest() -> None:
    """Card f waits on a: a moves f downstream (own 6) without f being a's parent."""
    tree = tree_of(SIX, ALL_OPEN, [*DIAMOND, (5, 0, WAITS)])
    assert tree.own[0] == SIX
    assert tree.parent[0] == 1


def test_a_closed_card_is_in_neither_the_forest_nor_the_weights() -> None:
    """With d closed, b and c have nothing to sit under."""
    tree = tree_of(SIX, [True, True, True, False, True, True], DIAMOND)
    assert tree.parent[1] == NONE
    assert tree.parent[D] == NONE
    assert tree.weight[D] == 0
    assert D not in tree.roots


def test_a_cycle_among_chosen_parents_is_cut_at_its_lowest_card() -> None:
    """Cards a and b enable each other: the lowest becomes the root, and both are weighed once."""
    tree = tree_of(2, [True, True], [(0, 1, ENABLES), (1, 0, ENABLES)])
    assert tree.parent == [NONE, 0]
    assert tree.roots == [0]
    assert tree.weight[0] == tree.own[0] + tree.weight[1]


def test_the_forest_is_rebuilt_from_parents_and_weights_alone() -> None:
    """What the layout needs, kids and roots in ascending order, comes from two arrays."""
    tree = tree_of(SIX, [True, True, True, False, True, True], DIAMOND)
    again = forest_of(tree.parent, tree.weight)
    assert again.kids == tree.kids
    assert again.roots == tree.roots
