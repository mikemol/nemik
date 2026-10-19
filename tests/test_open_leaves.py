# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W485: the open leaves of a queue, how many there are and how long they have waited."""

import json
from datetime import UTC, datetime
from pathlib import Path

from nemik.metrics import open_leaf_lines
from nemik.workrows import open_leaf_stamps

NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC)
HOUR = 3600
EARLY = "2026-10-19T08:00:00Z"
LATE = "2026-10-19T10:00:00Z"


def _card(
    symbol: str, status: str, issued: str, enables: list[str], waits: list[str]
) -> dict[str, object]:
    """Build one queue entry; an empty `issued` leaves issued_at out.

    Args:
        symbol: Its symbol.
        status: Its state.
        issued: Its issued_at stamp, or empty for none.
        enables: The cards it enables.
        waits: The cards it is blocked on.

    Returns:
        The entry.

    """
    card: dict[str, object] = {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": status,
        "enables": enables,
        "blocked_on": waits,
        "blocked_kind": "agent" if waits else None,
    }
    if issued:
        card["issued_at"] = issued
    return card


def _queue(first_issued: str = LATE) -> str:
    """Build a queue with leaves W1 and W4, an interior W3, a done W2 and a dropped W5.

    Args:
        first_issued: When W1 was issued, or empty for no issued_at.

    Returns:
        The queue text.

    """
    body: dict[str, object] = {
        "version": 1,
        "counter": 5,
        "project_root": "/fixture/alpha",
        "residue": [],
        "waypoints": [
            _card("W1", "ready", first_issued, [], []),
            _card("W2", "done", "2026-10-19T09:00:00Z", [], []),
            _card("W3", "ready", EARLY, ["W4"], []),
            _card("W4", "blocked", EARLY, [], ["W3"]),
            _card("W5", "dropped", "2026-10-19T07:00:00Z", [], []),
        ],
    }
    return json.dumps(body)


def test_only_open_cards_nothing_waits_on_are_leaves() -> None:
    """W1 and W4 are open leaves; W3 has W4 waiting on it, W2 is done and W5 dropped."""
    assert open_leaf_stamps(_queue()) == [EARLY, LATE]


def test_a_leaf_with_no_issue_time_is_left_out() -> None:
    """A card with no issued_at is not counted as new."""
    assert open_leaf_stamps(_queue(first_issued="")) == [EARLY]


def test_the_lines_carry_the_count_and_the_ages(tmp_path: Path) -> None:
    """Two leaves, 2 h and 4 h old: the count is 2, the oldest 4 h, the median the older of two."""
    repo = tmp_path / "alpha"
    repo.mkdir()
    (repo / "paths-forward.json").write_text(_queue())
    (repo / "paths-forward.ledger").write_text("")
    out = open_leaf_lines(tmp_path, NOW)
    four = 4 * HOUR
    assert 'nemik_open_leaves{repo="alpha"} 2' in out
    assert f'nemik_open_leaf_age_seconds{{repo="alpha",quantile="1"}} {four}' in out
    assert f'nemik_open_leaf_age_seconds{{repo="alpha",quantile="0.5"}} {four}' in out
