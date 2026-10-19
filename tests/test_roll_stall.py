# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W683: nemik-check warns on a repo that keeps rolling its tick at advanced 0."""

import json
from pathlib import Path

from nemik.adapter import queue_graph
from nemik.check import Finding, add_roll_warnings

IDLE = '2026-10-18T10:0{n}:00Z  tick  W1  advanced  unblock  "closed [rolled; advanced 0]"\n'
BUSY = '2026-10-18T10:0{n}:00Z  tick  W1  advanced  unblock  "closed [rolled; advanced 3]"\n'


def _repo(root: Path, ledger_lines: list[str]) -> dict[str, list[Finding]]:
    """Write one repo with a ready card and the given ledger, and run the roll check.

    Args:
        root: The fleet root.
        ledger_lines: The ledger's lines.

    Returns:
        The findings the check added, by repo.

    """
    queue = {
        "version": 1,
        "counter": 1,
        "project_root": "/fixture/alpha",
        "residue": [],
        "waypoints": [
            {
                "symbol": "W1",
                "title": "card W1",
                "status": "ready",
                "enables": [],
                "blocked_on": [],
                "blocked_kind": None,
            }
        ],
    }
    (root / "alpha").mkdir()
    (root / "alpha" / "paths-forward.json").write_text(json.dumps(queue))
    (root / "alpha" / "paths-forward.ledger").write_text("".join(ledger_lines))
    found: dict[str, list[Finding]] = {}
    graph = queue_graph("alpha", root / "alpha" / "paths-forward.json")
    add_roll_warnings(root, graph, found)
    return found


def test_two_idle_rolls_with_a_ready_card_warn(tmp_path: Path) -> None:
    """Two rolls at advanced 0 while a card is ready is a Warning on the repo."""
    found = _repo(tmp_path, [IDLE.format(n=1), IDLE.format(n=2)])
    assert [sev for sev, _, _ in found["alpha"]] == ["Warning"]
    assert "advanced 0" in found["alpha"][0][2]


def test_a_roll_that_advanced_a_card_ends_the_run(tmp_path: Path) -> None:
    """An idle roll behind a busy one does not warn."""
    assert not _repo(tmp_path, [IDLE.format(n=1), BUSY.format(n=2), IDLE.format(n=3)])


def test_one_idle_roll_does_not_warn(tmp_path: Path) -> None:
    """A single roll at advanced 0 is under the limit."""
    assert not _repo(tmp_path, [IDLE.format(n=1)])
