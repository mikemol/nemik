# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2391, W2407: the round does not drop a card being worked (luthen:W2894).

W2391 made the round's WIDTH a function of the ranked set. W2407 pins the working cards into the
round and fills the rest from the ready cards by rank, so a card's state moves only its own place.
"""

from nemik.roundcli import NO_LANDINGS, round_lines, size_for, stackable_of

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


def _lines(rows: list[dict[str, object]]) -> list[str]:
    """Draw the round the way nemik-rank --round does, with no landing history.

    Returns:
        Its printed lines: the header, an optional warning, then one line per card.

    """
    ranked = [(str(r["symbol"]), str(r["salience"]), str(r["title"])) for r in rows]
    working = [str(r["symbol"]) for r in rows if r["state"] == "working"]
    return round_lines("r", ranked, NO_LANDINGS, stackable_of(rows), working)


def _round(rows: list[dict[str, object]]) -> tuple[int, list[str]]:
    """Draw the round.

    Returns:
        The supply, and the symbols of the round in rank order.

    """
    lines = [line for line in _lines(rows) if line[:1].isspace()]
    return stackable_of(rows), [line.split()[1] for line in lines]


def _masks() -> list[frozenset[str]]:
    """Every subset of the cards, as a working set.

    Returns:
        The 256 working sets, the empty one first.

    """
    return [
        frozenset(card for i, card in enumerate(CARDS) if mask >> i & 1)
        for mask in range(1 << len(CARDS))
    ]


def test_taking_a_card_that_shares_a_file_leaves_the_round_as_it_was() -> None:
    """Luthen's W2894: taking A used to cut the supply from 5 to 4 and drop E."""
    before = _round(_rows(SHARED, frozenset()))
    after = _round(_rows(SHARED, frozenset({"A"})))
    assert before == (SIZE_IN_ROUND, ["A", "B", "C", "D", "E"])
    assert after == before


def test_a_working_card_is_in_the_round_whatever_its_rank() -> None:
    """nemik:W1059's invariant: a card being worked is never outside the round."""
    for layout in LAYOUTS:
        for taken in _masks():
            _, cards = _round(_rows(layout, taken))
            assert taken <= set(cards), (layout, sorted(taken), cards)


def test_a_working_card_stays_in_under_any_flip_of_another_card() -> None:
    """Luthen's A and B: flipping W941 or W1434 must not move a card that stays working."""
    for layout in LAYOUTS:
        for taken in _masks():
            for card in CARDS:
                flipped = taken ^ frozenset({card})
                _, now = _round(_rows(layout, flipped))
                for stay in taken & flipped:
                    assert stay in now, (layout, sorted(taken), card)


def test_the_room_the_working_cards_leave_is_filled_by_ready_rank() -> None:
    """The round is the working cards and the best ready cards, up to the width."""
    for layout in LAYOUTS:
        for taken in _masks():
            rows = _rows(layout, taken)
            size, _ = size_for("r", rows, NO_LANDINGS)
            _, cards = _round(rows)
            ready = [c for c in CARDS if c not in taken]
            room = max(size - len(taken), 0)
            assert set(cards) == taken | set(ready[:room]), (layout, sorted(taken))


def test_a_working_card_the_ranking_lacks_is_named() -> None:
    """The edge github-00 named: a working card the ranker left out gets a warning line."""
    ranked = [("A", "1", "A"), ("B", "1", "B")]
    lines = round_lines("r", ranked, NO_LANDINGS, 2, ["A", "Z"])
    named = [line for line in lines if line.startswith("warning:") and "Z" in line]
    assert len(named) == 1, lines
    assert [line.split()[1] for line in lines if line[:1].isspace()] == ["A", "B"]


def test_a_working_set_wider_than_the_width_is_the_round_and_a_warning() -> None:
    """Focus is forecast, not control: no ready fill, no refusal, the excess is a warning."""
    rows = _rows(SHARED, frozenset(CARDS))
    lines = _lines(rows)
    _, cards = _round(rows)
    assert cards == list(CARDS)
    assert any(line.startswith("warning:") for line in lines), lines
