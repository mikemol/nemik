"""nemik:W330: nemik-work leaves exactly one card working."""

from __future__ import annotations

import json
from pathlib import Path

from nemik.work import blockers, main, plan, working


def _queue(tmp_path: Path) -> Path:
    state = tmp_path / "q.json"
    state.write_text(
        json.dumps(
            {
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
        )
    )
    return state


def test_landed_blockers_are_done_or_dropped_and_the_rest_are_open(
    tmp_path: Path,
) -> None:
    # nemik:W443
    state = _queue(tmp_path)
    assert blockers(state, "W3") == ([], ["W1", "W9"])
    assert blockers(state, "W4") == (["W2", "other:W7"], [])
    assert blockers(state, "W2") == ([], [])


def test_a_card_with_open_blockers_is_refused_and_a_landed_one_goes_through(
    tmp_path: Path, capsys
) -> None:
    state = _queue(tmp_path)
    assert main(["W4", "--state", str(state), "--dry-run"]) == 2
    assert "blocked on W2, other:W7" in capsys.readouterr().err
    assert main(["W4", "--state", str(state), "--dry-run", "--force"]) == 0
    assert main(["W5", "--state", str(state), "--dry-run"]) == 0
    assert "cleared landed blocker(s): W1" in capsys.readouterr().out


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
