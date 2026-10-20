# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W769: the oldest open cards of the fleet, oldest first, with what kind of old each is."""

from datetime import UTC, datetime

from nemik.history import oldest_cards

NOW = datetime(2026, 10, 20, tzinfo=UTC)


def _card(symbol: str, status: str, issued: str, **more: object) -> dict[str, object]:
    """Build one queue card.

    Args:
        symbol: Its W<n>.
        status: Its status.
        issued: Its issued_at.
        **more: Further fields.

    Returns:
        The card.

    """
    return {
        "symbol": symbol,
        "status": status,
        "issued_at": issued,
        "title": f"title {symbol}",
        **more,
    }


def test_the_oldest_open_cards_come_first_with_their_kind_of_old() -> None:
    """Done, dropped and undated cards are left out; ready is untouched, blocked stuck."""
    docs: dict[str, object] = {
        "a": {
            "waypoints": [
                _card("W1", "done", "2026-09-01T00:00:00Z"),
                _card("W2", "ready", "2026-09-20T00:00:00Z"),
                _card("W3", "blocked", "2026-09-10T00:00:00Z", blocked_on=["b:W9"]),
                _card("W4", "working", "2026-10-19T00:00:00Z"),
                {"symbol": "W5", "status": "ready", "title": "undated"},
            ]
        },
        "b": {"waypoints": [_card("W9", "ready", "2026-09-15T00:00:00Z")]},
    }
    got = oldest_cards(docs, NOW, 3)
    assert [r["cite"] for r in got] == ["a:W3", "b:W9", "a:W2"]
    assert (got[0]["age_days"], got[0]["flag"], got[0]["blocked_on"]) == (
        "40.0",
        "stuck",
        "b:W9",
    )
    assert got[1]["flag"] == "untouched"


def test_a_limit_cuts_the_list_and_an_unreadable_queue_adds_nothing() -> None:
    """Two cards, limit one; and a repo whose queue is not a dict adds none."""
    docs: dict[str, object] = {
        "a": {
            "waypoints": [
                _card("W1", "ready", "2026-09-01T00:00:00Z"),
                _card("W2", "ready", "2026-09-02T00:00:00Z"),
            ]
        },
        "b": "unreadable",
    }
    assert [r["cite"] for r in oldest_cards(docs, NOW, 1)] == ["a:W1"]
