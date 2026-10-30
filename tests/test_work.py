# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W330: nemik-work leaves exactly one card working."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from nemik.work import blockers, main, plan, working

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _queue(tmp_path: Path) -> Path:
    state = tmp_path / "q.json"
    payload2: dict[str, object] = {
        "waypoints": [
            {"symbol": "W1", "status": "done"},
            {"symbol": "W2", "status": "ready"},
            {"symbol": "W3", "status": "blocked", "blocked_on": ["W1", "W9"]},
            {
                "symbol": "W4",
                "status": "blocked",
                "blocked_on": ["W2", "other:W7"],
            },
            {"symbol": "W5", "status": "blocked", "blocked_on": ["W1"]},
        ],
        "residue": [{"symbol": "W9"}],
    }
    state.write_text(json.dumps(payload2))
    return state


def test_landed_blockers_are_done_or_dropped_and_the_rest_are_open(
    tmp_path: Path,
) -> None:
    """Landed blockers are done or dropped and the rest are open."""
    # nemik:W443
    state = _queue(tmp_path)
    assert blockers(state, "W3") == ([], ["W1", "W9"])
    assert blockers(state, "W4") == (["W2", "other:W7"], [])
    assert blockers(state, "W2") == ([], [])


def test_a_card_with_open_blockers_is_refused_and_a_landed_one_goes_through(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A card with open blockers is refused and a landed one goes through."""
    state = _queue(tmp_path)
    assert main(["W4", "--state", str(state), "--dry-run"]) == 2
    assert "blocked on W2, other:W7" in capsys.readouterr().err
    assert main(["W4", "--state", str(state), "--dry-run", "--force"]) == 0
    assert main(["W5", "--state", str(state), "--dry-run"]) == 0
    assert "cleared landed blocker(s): W1" in capsys.readouterr().out


def test_the_plan_marks_the_target_and_demotes_no_other_card() -> None:
    """The plan marks the target and demotes no other card."""
    # nemik:W1006: no one-working-card limit (operator 2026-10-15, line 68086)
    assert plan(["W1", "W2"], "W3") == [("W3", "working")]
    assert plan(["W1", "W2"], "W2") == []  # W2 already working, W1 stays working
    assert plan([], "W5") == [("W5", "working")]
    assert plan(["W5"], "W5") == []  # nothing to do


def test_working_reads_the_queue_file(tmp_path: Path) -> None:
    """Working reads the queue file."""
    state = tmp_path / "q.json"
    waypoints = [
        {"symbol": "W1", "status": "working"},
        {"symbol": "W2", "status": "ready"},
        {"symbol": "W3", "status": "working"},
    ]
    payload: dict[str, object] = {"waypoints": waypoints}
    state.write_text(json.dumps(payload))
    assert working(state) == ["W1", "W3"]
