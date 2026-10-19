# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W485: where a repo's working ticks went, by directed, leaf and interior cards."""

import json
from pathlib import Path

from nemik.metrics import working_tick_lines
from nemik.workrows import tick_kinds, working_rows

TICKS = [
    ("2026-10-18T10:00:00Z", "W1"),
    ("2026-10-18T10:05:00Z", "W2"),
    ("2026-10-18T10:10:00Z", "W2"),
    ("2026-10-18T10:15:00Z", "W3"),
    ("2026-10-18T10:20:00Z", "W9"),
]
LEDGER = "".join(
    f'{stamp}  tick  {symbol}  advanced  unblock  "worked"\n' for stamp, symbol in TICKS
)


def _queue() -> str:
    """Write a queue where W1 is directed, W2 a leaf, W3 interior, and W9 is not a card.

    Returns:
        The queue text.

    """
    cards: list[dict[str, object]] = [
        {
            "symbol": "W1",
            "title": "asked for",
            "status": "ready",
            "enables": [],
            "blocked_on": [],
            "blocked_kind": None,
            "caused_by": "peer",
        },
        {
            "symbol": "W2",
            "title": "nothing waits",
            "status": "ready",
            "enables": [],
            "blocked_on": [],
            "blocked_kind": None,
            "caused_by": "W3",
        },
        {
            "symbol": "W3",
            "title": "unblocks W4",
            "status": "ready",
            "enables": ["W4"],
            "blocked_on": [],
            "blocked_kind": None,
        },
        {
            "symbol": "W4",
            "title": "waits on W3",
            "status": "blocked",
            "enables": [],
            "blocked_on": ["W3"],
            "blocked_kind": "agent",
        },
    ]
    body: dict[str, object] = {
        "version": 1,
        "counter": 4,
        "project_root": "/fixture/alpha",
        "residue": [],
        "waypoints": cards,
    }
    return json.dumps(body)


def test_ticks_are_counted_by_kind() -> None:
    """One directed tick, two leaf ticks, one interior tick; the tick on a non-card is dropped."""
    kinds = tick_kinds(working_rows(TICKS, _queue()))
    assert kinds == {"directed": 1, "leaf": 2, "interior": 1}


def test_a_fleet_prints_one_line_per_repo_and_kind(tmp_path: Path) -> None:
    """The metrics lines carry the same counts, labelled by repo and kind."""
    repo = tmp_path / "alpha"
    repo.mkdir()
    (repo / "paths-forward.json").write_text(_queue())
    (repo / "paths-forward.ledger").write_text(LEDGER)
    out = working_tick_lines(tmp_path)
    assert 'nemik_working_ticks{repo="alpha",kind="directed"} 1' in out
    assert 'nemik_working_ticks{repo="alpha",kind="leaf"} 2' in out
    assert 'nemik_working_ticks{repo="alpha",kind="interior"} 1' in out
