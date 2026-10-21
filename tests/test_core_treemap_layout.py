# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W827: the treemap model's strip layout over plain data."""

from nemik.core.treemap import ENABLES, NONE, Cells, Tree, ordered_treemap, tree_of

SQUARE = (0.0, 0.0, 100.0, 100.0)
MARGINS = (4.0, 12.0)
THREE_TO_ONE = Tree([NONE, NONE], [[], []], [3, 1], [3, 1], [0, 1])
TWO_EQUAL = Tree([NONE, NONE], [[], []], [1, 1], [1, 1], [0, 1])


def _box(cells: Cells, card: int) -> tuple[float, float, float, float]:
    """Read one card's cell as (x, y, width, height).

    Returns:
        The rectangle.

    """
    return (cells.x[card], cells.y[card], cells.w[card], cells.h[card])


def test_a_lone_card_fills_the_rectangle() -> None:
    """One root takes the whole area, at depth zero, with no header."""
    cells = ordered_treemap(tree_of(1, [True], []), [0], SQUARE, MARGINS)
    assert cells.placed == [True]
    assert _box(cells, 0) == SQUARE
    assert cells.depth[0] == 0
    assert not cells.head[0]


def test_a_strip_closes_when_the_next_card_would_worsen_its_aspect() -> None:
    """Weights 3 and 1 in a square: the 3 is a strip of 100 by 75, the 1 sits under it."""
    cells = ordered_treemap(THREE_TO_ONE, [0, 1], SQUARE, MARGINS)
    assert _box(cells, 0) == (0.0, 0.0, 100.0, 75.0)
    assert _box(cells, 1) == (0.0, 75.0, 100.0, 25.0)


def test_a_card_with_work_beneath_it_is_a_frame_with_a_header() -> None:
    """The kid sits inside the parent's margins, one depth down, below the header strip."""
    tree = tree_of(2, [True, True], [(0, 1, ENABLES)])
    cells = ordered_treemap(tree, [1], SQUARE, MARGINS)
    assert _box(cells, 1) == SQUARE
    assert cells.head[1] == MARGINS[1]
    assert _box(cells, 0) == (4.0, 12.0, 92.0, 84.0)
    assert cells.depth[0] == 1


def test_no_room_places_every_card_at_the_corner_with_nothing() -> None:
    """A rectangle without width gives each card a point."""
    cells = ordered_treemap(THREE_TO_ONE, [0, 1], (7.0, 9.0, 0.0, 50.0), MARGINS)
    assert cells.placed == [True, True]
    assert _box(cells, 0) == (7.0, 9.0, 0.0, 0.0)
    assert _box(cells, 1) == (7.0, 9.0, 0.0, 0.0)


def test_cards_not_in_the_order_sort_after_those_that_are() -> None:
    """With only card 1 ranked it is laid first; two equal cards share a strip, so left to right."""
    cells = ordered_treemap(TWO_EQUAL, [1], SQUARE, MARGINS)
    assert cells.x[1] < cells.x[0]
    assert cells.y[1] == cells.y[0]
