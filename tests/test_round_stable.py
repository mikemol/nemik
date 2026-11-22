# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2391: the round does not change when a card in it is taken (luthen:W2894)."""

from nemik.roundcli import NO_LANDINGS, round_lines, stackable_of

CARDS = "ABCDEFGH"
DISJOINT = {card: [card.lower()] for card in CARDS}
# A, B, C and D share file x; E to H are disjoint: the run luthen's round alternated over
SHARED = {**DISJOINT, "A": ["x"], "B": ["x"], "C": ["x"], "D": ["x"]}
CHAIN = {**DISJOINT, "A": ["x"], "B": ["x", "y"], "C": ["y", "z"], "D": ["z"]}
LAYOUTS = [DISJOINT, SHARED, CHAIN]
SIZE_IN_ROUND = 5


def _rows(
    layout: dict[str, list[str]], working: frozenset[str]
) -> list[dict[str, object]]:
    """Give the ranking as the round reads it: every card, in rank order, working ones too.

    Returns:
        One row per card, best first, with its state and manifest.

    """
    return [
        {
            "symbol": card,
            "salience": "1",
            "title": card,
            "state": "working" if card in working else "ready",
            "manifest": layout[card],
        }
        for card in CARDS
    ]


def _round(rows: list[dict[str, object]]) -> tuple[int, list[str]]:
    """Draw the round the way nemik-rank --round does, with no landing history.

    Returns:
        The supply, and the symbols of the round in rank order.

    """
    ranked = [(str(r["symbol"]), str(r["salience"]), str(r["title"])) for r in rows]
    stackable = stackable_of(rows)
    lines = round_lines("r", ranked, NO_LANDINGS, stackable)
    return stackable, [line.split()[1] for line in lines[1:]]


def test_taking_a_card_that_shares_a_file_leaves_the_round_as_it_was() -> None:
    """Luthen's W2894: taking A used to cut the supply from 5 to 4 and drop E."""
    before = _round(_rows(SHARED, frozenset()))
    after = _round(_rows(SHARED, frozenset({"A"})))
    assert before == (SIZE_IN_ROUND, ["A", "B", "C", "D", "E"])
    assert after == before


def test_no_set_of_working_cards_changes_the_round_in_any_layout() -> None:
    """The invariant: the round is a function of the ranked set, not of its cards' states."""
    for layout in LAYOUTS:
        base = _round(_rows(layout, frozenset()))
        for mask in range(1, 1 << len(CARDS)):
            taken = frozenset(card for i, card in enumerate(CARDS) if mask >> i & 1)
            assert _round(_rows(layout, taken)) == base, (layout, sorted(taken))


def test_a_working_card_counts_like_a_ready_one() -> None:
    """The stated cost: the supply is no longer 'beside the work in progress'."""
    rows = _rows(DISJOINT, frozenset({"A", "B"}))
    assert stackable_of(rows) == len(CARDS)
