# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W454: repo health computed from plain Cards and ask rows alone, no graph."""

from nemik.cards import Card
from nemik.health import health_cards


def test_signals_from_cards_alone() -> None:
    cards = {
        "r:W1": Card("r:W1", "blocked", "", (), (), ticks_blocked=9),
        "r:W2": Card("r:W2", "ready", "", (), ()),
        "r:W3": Card("r:W3", "done", "", (), ()),
        "s:W1": Card("s:W1", "blocked", "", (), (), ticks_blocked=99),
    }
    asks = [
        {"category": "needs-you", "ref": "r:W1"},
        {"category": "fyi", "ref": "r:W2"},
        {"category": "needs-you", "ref": "s:W1"},
    ]
    limits = {
        "blocked_share": (0.4, 0.9),
        "oldest_block_ticks": (8, 16),
        "asks_owed": (2, 5),
    }
    found = health_cards(cards, asks, "r", limits)
    assert found.blocked_share == 0.5
    assert found.oldest_block_ticks == 9
    assert found.asks_owed == 1
    assert found.status == "amber"
    assert len(found.reasons) == 2
