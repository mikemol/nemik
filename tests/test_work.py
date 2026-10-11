"""nemik:W330: nemik-work leaves exactly one card working."""

from __future__ import annotations

import json
from pathlib import Path

from nemik.work import plan, working


def test_the_plan_returns_the_others_to_ready_and_marks_the_target() -> None:
    assert plan(["W1", "W2"], "W3") == [
        ("W1", "ready"),
        ("W2", "ready"),
        ("W3", "working"),
    ]
    assert plan(["W1", "W2"], "W2") == [("W1", "ready")]  # W2 already working
    assert plan([], "W5") == [("W5", "working")]
    assert plan(["W5"], "W5") == []  # nothing to do


def test_working_reads_the_queue_file(tmp_path: Path) -> None:
    state = tmp_path / "q.json"
    waypoints = [
        {"symbol": "W1", "status": "working"},
        {"symbol": "W2", "status": "ready"},
        {"symbol": "W3", "status": "working"},
    ]
    state.write_text(json.dumps({"waypoints": waypoints}))
    assert working(state) == ["W1", "W3"]
