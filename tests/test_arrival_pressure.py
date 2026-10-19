# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W609: arrivals against completions over the same trailing 7 days, as two gauges."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nemik import metrics
from nemik.adapter import queue_graph
from nemik.metrics import arrivals_within, flow_lines, flow_sample

NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC)
WEEK = 7 * 86400
DAYS = 7
ARRIVED = 4
COMPLETED = 2


def _card(symbol: str, issued: str) -> dict[str, object]:
    """Build one ready queue entry issued at a stamp.

    Args:
        symbol: Its symbol.
        issued: Its issued_at stamp.

    Returns:
        The entry.

    """
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": "ready",
        "issued_at": issued,
        "enables": [],
        "blocked_on": [],
        "blocked_kind": None,
    }


def _two_completed(repo_dir: Path, since: str) -> int:
    """Answer as a git history that shows two cards closing in the window.

    Args:
        repo_dir: The repo's directory, unused.
        since: The window start, unused.

    Returns:
        Two.

    """
    del repo_dir, since
    return COMPLETED


def _fleet(root: Path) -> None:
    """Lay out repo alpha with four cards issued in the week and one issued before it.

    Args:
        root: The fleet root.

    """
    cards = [_card(f"W{n}", f"2026-10-1{n}T08:00:00Z") for n in (3, 4, 5, 6)]
    cards.append(_card("W9", "2026-09-01T08:00:00Z"))
    body: dict[str, object] = {
        "version": 1,
        "counter": 9,
        "project_root": "/fixture/alpha",
        "residue": [],
        "waypoints": cards,
    }
    (root / "alpha").mkdir()
    (root / "alpha" / "paths-forward.json").write_text(json.dumps(body))


def test_pressure_and_net_inflow_over_the_same_window() -> None:
    """Four arrived and two completed in seven days: pressure 2, net inflow 2/7 a day."""
    pressure, net = flow_sample(ARRIVED, COMPLETED, DAYS)
    assert pressure == ARRIVED / COMPLETED
    assert net == (ARRIVED - COMPLETED) / DAYS


def test_pressure_is_absent_without_completions_but_net_inflow_is_not() -> None:
    """A ratio over zero is absent, not zero; the net inflow still reads."""
    pressure, net = flow_sample(ARRIVED, 0, DAYS)
    assert pressure is None
    assert net == ARRIVED / DAYS


def test_the_scale_a_ratio_hides_shows_in_the_net_inflow() -> None:
    """2 over 1 and 200 over 100 have the same pressure and very different inflow."""
    small = flow_sample(2, 1, DAYS)
    large = flow_sample(200, 100, DAYS)
    assert small[0] == large[0]
    assert small[1] != large[1]


def test_only_cards_issued_in_the_window_arrive(tmp_path: Path) -> None:
    """The card issued in September is outside the week."""
    _fleet(tmp_path)
    graph = queue_graph("alpha", tmp_path / "alpha" / "paths-forward.json")
    assert arrivals_within(graph, NOW, WEEK)["alpha"] == ARRIVED


def test_the_lines_carry_both_gauges_for_a_repo_with_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With two completions in the week, alpha prints pressure 2.000 and net inflow 0.29."""
    _fleet(tmp_path)
    monkeypatch.setattr(metrics, "completed_in", _two_completed)
    graph = queue_graph("alpha", tmp_path / "alpha" / "paths-forward.json")
    out = flow_lines(tmp_path, graph, NOW)
    assert 'nemik_arrival_pressure{repo="alpha"} 2.000' in out
    assert 'nemik_net_inflow_per_day{repo="alpha"} 0.29' in out
