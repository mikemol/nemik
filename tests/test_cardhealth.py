# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W977: cardhealth's verdict agrees with nemik.health.health_cards on a table of repos."""

from typing import TYPE_CHECKING

from nemik.cardhealth import STATUSES, share_of, verdict
from nemik.cards import Card
from nemik.health import health_cards

if TYPE_CHECKING:
    from nemik.blocks import AskRow

LIMITS = {
    "blocked_share": (0.4, 0.7),
    "oldest_block_ticks": (4.0, 8.0),
    "asks_owed": (1.0, 3.0),
}


def card(symbol: str, state: str, ticks: int = 0) -> Card:
    """Build one card of repo alpha.

    Returns:
        The card.

    """
    return Card(f"alpha:{symbol}", state, "t", (), (), ticks)


def judged(cards: list[Card], owed: int) -> tuple[str, float, int, list[str]]:
    """Run the plain verdict the way health_cards reads its numbers.

    Returns:
        (status, blocked share rounded to 3 places, oldest block ticks, reasons).

    """
    open_cards = [c for c in cards if not c.done]
    blocked = [c for c in open_cards if c.state == "blocked"]
    share = share_of(len(blocked), len(open_cards))
    ticks = max((c.ticks_blocked for c in blocked), default=0)
    seen = [
        ("blocked_share", share),
        ("oldest_block_ticks", float(ticks)),
        ("asks_owed", float(owed)),
    ]
    worst, reasons = verdict(seen, LIMITS)
    return STATUSES[worst], round(share, 3), ticks, reasons


def test_the_verdict_agrees_with_health_cards_on_a_table() -> None:
    """Green, amber by one signal, red by two, and an empty repo, each equal to the reference."""
    table = [
        ([card("W1", "ready"), card("W2", "ready")], 0),
        ([card("W1", "blocked", 5), card("W2", "ready"), card("W3", "ready")], 0),
        ([card("W1", "blocked", 9), card("W2", "blocked", 2), card("W3", "ready")], 3),
        ([card("W1", "done")], 0),
        ([], 1),
    ]
    for cards, owed in table:
        by_cite = {c.cite: c for c in cards}
        asks: list[AskRow] = [{"category": "needs-you", "ref": "alpha:W9"}] * owed
        ref = health_cards(by_cite, asks, "alpha", LIMITS)
        assert judged(cards, owed) == (
            ref.status,
            ref.blocked_share,
            ref.oldest_block_ticks,
            ref.reasons,
        )
