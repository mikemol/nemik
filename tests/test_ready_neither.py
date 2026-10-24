# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W489: a ready card left untouched past how long small cards take to finish."""

import json
from pathlib import Path

from nemik.check import Finding, add_ready_neither_infos, ready_neither
from nemik.workrows import NO_BOUND, upper_quantile

NOW = "2026-01-10T00:00:00Z"
DAY = 86400.0
FINISHED = 10


def _done(symbol: str) -> dict[str, object]:
    """Build a small card issued on Jan 1 and completed on Jan 2, one day later.

    Args:
        symbol: Its symbol.

    Returns:
        The entry.

    """
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": "done",
        "size_class": "small",
        "issued_at": "2026-01-01T00:00:00Z",
        "completed": "2026-01-02T00:00:00Z",
        "enables": [],
        "blocked_on": [],
        "blocked_kind": None,
    }


def _ready(symbol: str, issued: str, worked: str = "") -> dict[str, object]:
    """Build a ready card issued at a stamp and optionally last worked at another.

    Args:
        symbol: Its symbol.
        issued: Its issued_at.
        worked: Its last_worked, or empty for none.

    Returns:
        The entry.

    """
    card: dict[str, object] = {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": "ready",
        "issued_at": issued,
        "enables": [],
        "blocked_on": [],
        "blocked_kind": None,
    }
    if worked:
        card["last_worked"] = worked
    return card


def _fleet(root: Path, finished: int) -> None:
    """Lay out repo alpha with finished small cards and three ready cards.

    Args:
        root: The fleet root.
        finished: How many done small cards to write.

    """
    cards = [_done(f"W{n}") for n in range(1, finished + 1)]
    cards += [
        _ready("W91", "2026-01-01T00:00:00Z"),
        _ready("W92", "2026-01-09T20:00:00Z"),
        _ready("W93", "2026-01-01T00:00:00Z", "2026-01-09T23:00:00Z"),
    ]
    body: dict[str, object] = {
        "version": 1,
        "counter": 99,
        "project_root": "/fixture/alpha",
        "residue": [],
        "waypoints": cards,
    }
    (root / "alpha").mkdir()
    (root / "alpha" / "paths-forward.json").write_text(json.dumps(body))


def test_the_bound_is_the_nearest_rank_quantile() -> None:
    """The 0.9 quantile of ten observations is the ninth smallest; none gives no bound."""
    values = [float(n) for n in range(1, FINISHED + 1)]
    assert upper_quantile(values, 0.9) == values[-2]
    assert upper_quantile([], 0.9) == NO_BOUND


def test_a_card_untouched_past_the_bound_is_late(tmp_path: Path) -> None:
    """Only W91 is late: W92 is recent and W93 was worked last night."""
    _fleet(tmp_path, FINISHED)
    bound, late = ready_neither(tmp_path, NOW)
    assert bound == DAY
    assert [symbol for _, symbol in late["alpha"]] == ["W91"]


def test_too_few_finished_cards_learn_no_bound(tmp_path: Path) -> None:
    """With nine finished small cards no bound is learned and nothing is late."""
    _fleet(tmp_path, FINISHED - 1)
    bound, late = ready_neither(tmp_path, NOW)
    assert bound == NO_BOUND
    assert not late


def test_the_warning_is_one_row_per_repo_with_the_count(tmp_path: Path) -> None:
    """A repo gets one Warning naming how many ready cards are late and the oldest."""
    _fleet(tmp_path, FINISHED)
    found: dict[str, list[Finding]] = {}
    add_ready_neither_infos(tmp_path, found)
    rows = found["alpha"]
    assert [sev for sev, _, _ in rows] == ["Warning"]
    assert "oldest W91" in rows[0][2]
