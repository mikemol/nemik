# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W699: a card that has waited longer on its blocker raises that blocker's salience."""

import json
from fractions import Fraction
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.salience import audit, load_wait_weight

WEIGHT = Fraction(1)
OLD_WAIT = 10


def _card(
    symbol: str, status: str, enables: list[str], waits: int
) -> dict[str, object]:
    """Build one queue entry.

    Args:
        symbol: Its symbol.
        status: ready or blocked.
        enables: The cards it enables.
        waits: Its ticks_blocked.

    Returns:
        The entry.

    """
    blocked = status == "blocked"
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": status,
        "enables": enables,
        "blocked_on": [f"W{int(symbol[1:]) - 1}"] if blocked else [],
        "blocked_kind": "agent" if blocked else None,
        "ticks_blocked": waits,
    }


def _graph(tmp_path: Path) -> Graph:
    """Two ready cards, each with one waiter; W2 has waited long, W4 not at all.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The queue graph of repo alpha.

    """
    queue = {
        "version": 1,
        "counter": 4,
        "project_root": "/fixture/alpha",
        "residue": [],
        "waypoints": [
            _card("W1", "ready", ["W2"], 0),
            _card("W2", "blocked", [], OLD_WAIT),
            _card("W3", "ready", ["W4"], 0),
            _card("W4", "blocked", [], 0),
        ],
    }
    path = tmp_path / "paths-forward.json"
    path.write_text(json.dumps(queue))
    return queue_graph("alpha", path)


def _salience(tmp_path: Path, weight: Fraction) -> dict[str, Fraction]:
    """Give each ready card's flow salience under a wait weight.

    Args:
        tmp_path: A scratch directory.
        weight: The demand one waited tick adds.

    Returns:
        ref -> salience.

    """
    result = audit(_graph(tmp_path), "alpha", wait_weight=weight)
    return {row.ref: row.new for row in result.rows}


def test_without_a_weight_equal_waits_rank_equal(tmp_path: Path) -> None:
    """Zero weight is the ranking as it was: the two blockers tie."""
    rows = _salience(tmp_path, Fraction(0))
    assert rows["alpha:W1"] == rows["alpha:W3"]


def test_a_longer_wait_raises_its_blockers_salience(tmp_path: Path) -> None:
    """With a weight, the blocker of the card that has waited ten ticks outranks the other."""
    rows = _salience(tmp_path, WEIGHT)
    assert rows["alpha:W1"] > rows["alpha:W3"]


def test_the_table_is_read_and_absence_is_zero() -> None:
    """The packaged table is off, a given one is read, and no table means zero."""
    assert load_wait_weight() == 0
    assert load_wait_weight("[wait_age]\nper_tick = 2\n") == Fraction(2)
    assert load_wait_weight("[other]\nx = 1\n") == 0
