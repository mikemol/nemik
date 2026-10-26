# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1128: --oldest takes a filter, and N counts only the cards the filter keeps."""

from datetime import UTC, datetime

from nemik.history import oldest_cards
from nemik.where import parse

NOW = datetime(2026, 10, 20, tzinfo=UTC)


def _card(symbol: str, status: str, issued: str, waits: list[str]) -> dict[str, object]:
    """Build one queue card.

    Returns:
        The card, issued at `issued`, waiting on `waits`.

    """
    return {
        "symbol": symbol,
        "status": status,
        "issued_at": issued,
        "title": f"title {symbol}",
        "blocked_on": waits,
    }


DOCS: dict[str, object] = {
    "a": {
        "waypoints": [
            _card("W1", "blocked", "2026-09-01T00:00:00Z", ["b:W9"]),
            _card("W2", "blocked", "2026-09-02T00:00:00Z", ["operator"]),
            _card("W3", "ready", "2026-09-20T00:00:00Z", []),
            _card("W4", "ready", "2026-10-19T12:00:00Z", []),
        ]
    },
    "b": {"waypoints": [_card("W9", "ready", "2026-09-15T00:00:00Z", [])]},
}


def test_the_oldest_two_that_are_not_blocked_skip_the_blocked_ones() -> None:
    """Without the filter the oldest two are the blocked cards; with it, two ready ones."""
    plain = [r["cite"] for r in oldest_cards(DOCS, NOW, 2)]
    assert plain == ["a:W1", "a:W2"]
    keep = tuple(parse("not blocked_on=*"))
    assert [r["cite"] for r in oldest_cards(DOCS, NOW, 2, keep)] == ["b:W9", "a:W3"]


def test_a_filter_by_status_age_and_repo_combines() -> None:
    """The ask's example: ready, waiting on nothing, older than two days."""
    keep = tuple(parse("status=ready and not blocked_on=* and age>2d and repo=a"))
    assert [r["cite"] for r in oldest_cards(DOCS, NOW, 5, keep)] == ["a:W3"]
