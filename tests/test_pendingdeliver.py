# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Tests for pendingdeliver: letters for cards the writer closed (nemik:W889)."""

import json
from datetime import date
from pathlib import Path

from nemik.pendingdeliver import since_day, sweep
from nemik.witnesses import RECORD

TODAY = date(2026, 10, 23)


def _queue(root: Path, repo: str, waypoints: list[dict[str, object]]) -> None:
    path = root / repo / ".claude" / "paths-forward.json"
    path.parent.mkdir(parents=True)
    (root / repo / "inbox").mkdir()
    body: dict[str, object] = {
        "version": 1,
        "counter": 20,
        "project_root": f"/fixture/{repo}",
        "residue": [],
        "waypoints": waypoints,
    }
    path.write_text(json.dumps(body), encoding="utf-8")


def _fleet(root: Path, completed: str) -> None:
    _queue(
        root,
        "a",
        [{"symbol": "W1", "title": "t", "status": "done", "completed": completed}],
    )
    _queue(
        root,
        "b",
        [
            {
                "symbol": "W2",
                "title": "waits",
                "status": "blocked",
                "blocked_on": ["a:W1"],
                "blocked_kind": "agent",
            }
        ],
    )


def test_since_day_counts_back_from_today() -> None:
    """Three days before the 23rd is the 20th."""
    assert since_day(TODAY, 3) == "20261020"


def test_a_recently_closed_card_writes_one_letter_once(tmp_path: Path) -> None:
    """The waiter's inbox gets a letter, the record names the edge, a rerun writes nothing."""
    _fleet(tmp_path, "20261022T010101Z")
    first = sweep(tmp_path, TODAY)
    assert len(first) == 1
    assert first[0].parent == tmp_path / "b" / "inbox"
    assert "a:W1" in (tmp_path / RECORD).read_text(encoding="utf-8")
    assert sweep(tmp_path, TODAY) == []


def test_an_old_closed_card_writes_nothing(tmp_path: Path) -> None:
    """A card closed before the cutoff is not announced."""
    _fleet(tmp_path, "20261001T010101Z")
    assert sweep(tmp_path, TODAY) == []
