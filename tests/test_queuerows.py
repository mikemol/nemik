# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W931: a repo's ready cards as a queue: place, wait, and how many newer cards are ahead."""

import json
from datetime import UTC, datetime
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.queuerows import UNKNOWN, fleet_queues, queue_rows

NOW = datetime(2026, 10, 10, 0, 0, tzinfo=UTC)
WAITED_A = 9.0
WAITED_B = 7.0


def _card(
    symbol: str,
    status: str,
    issued: str | None,
    enables: list[str] | None = None,
    blocked_on: list[str] | None = None,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": status,
        "enables": enables or [],
        "touches": [],
        "blocked_on": blocked_on or [],
        "blocked_kind": "agent" if blocked_on else None,
        "next_bounded_step": "do it",
        "evidence": "",
        "issued_at": issued,
        "last_worked": None,
        "ticks_blocked": 0,
    }


def _repo(root: Path, cards: list[dict[str, object]]) -> Graph:
    path = root / "alpha.json"
    body: dict[str, object] = {
        "version": 1,
        "counter": 10,
        "project_root": "/fixture/alpha",
        "residue": [],
        "waypoints": cards,
    }
    path.write_text(json.dumps(body), encoding="utf-8")
    return queue_graph("alpha", path, frozenset({"alpha"}))


def test_a_newer_card_with_work_behind_it_passes_an_older_one(tmp_path: Path) -> None:
    """W1 is oldest and bare; W2 is newer and a waiting card depends on it: W2 ranks first."""
    g = _repo(
        tmp_path,
        [
            _card("W1", "ready", "2026-10-01T00:00:00Z"),
            _card("W2", "ready", "2026-10-03T00:00:00Z", enables=["W3"]),
            _card("W3", "blocked", "2026-10-03T00:00:00Z", blocked_on=["W2"]),
        ],
    )
    rows = queue_rows(g, "alpha", NOW)
    assert [row.cite for row in rows] == ["alpha:W2", "alpha:W1"]
    assert [row.place for row in rows] == [1, 2]
    by_cite = {row.cite: row for row in rows}
    assert by_cite["alpha:W1"].overtaken_by == 1
    assert by_cite["alpha:W2"].overtaken_by == 0
    assert by_cite["alpha:W1"].waited_days == WAITED_A
    assert by_cite["alpha:W2"].waited_days == WAITED_B


def test_a_card_with_no_issue_stamp_has_an_unknown_wait(tmp_path: Path) -> None:
    """No stamp is -1 and passed by no one, never a guessed age."""
    g = _repo(tmp_path, [_card("W1", "ready", None)])
    (row,) = queue_rows(g, "alpha", NOW)
    assert row.waited_days == UNKNOWN
    assert row.overtaken_by == 0


def test_the_fleet_names_each_repo(tmp_path: Path) -> None:
    """With a repo named only its queue is built, keyed by the repo."""
    g = _repo(tmp_path, [_card("W1", "ready", "2026-10-01T00:00:00Z")])
    assert list(fleet_queues(g, ["alpha"], NOW)) == ["alpha"]
