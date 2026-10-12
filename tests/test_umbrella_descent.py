"""nemik:W405: a card waiting on another repo's umbrella is told which open steps to cite instead."""

from __future__ import annotations

import json
from pathlib import Path

from nemik.check import survey


def _write(root: Path, repo: str, cards: list[tuple[str, str, list[str]]]) -> None:
    queue = root / repo / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    waypoints = [
        {
            "symbol": sym,
            "title": sym,
            "status": status,
            "next_bounded_step": "x",
            **({"blocked_on": on, "blocked_kind": "agent"} if on else {}),
        }
        for sym, status, on in cards
    ]
    queue.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": "/x",
                "counter": len(cards),
                "residue": [],
                "waypoints": waypoints,
            }
        )
    )


def _hints(root: Path) -> dict[str, str]:
    return {
        sym: msg
        for repo, _, findings in survey(root)
        for sev, sym, msg in findings
        if repo == "a" and sev == "Info"
    }


def test_an_umbrella_is_descended_through_umbrellas_to_its_steps(
    tmp_path: Path,
) -> None:
    # b:W1 is an umbrella over b:W2 (itself an umbrella over b:W3, b:W4) and b:W5.
    _write(
        tmp_path,
        "b",
        [
            ("W1", "blocked", ["W2", "W5"]),
            ("W2", "blocked", ["W3", "W4"]),
            ("W3", "ready", []),
            ("W4", "ready", []),
            ("W5", "ready", []),
        ],
    )
    _write(tmp_path, "a", [("W1", "blocked", ["b:W1"])])
    hint = _hints(tmp_path)["W1"]
    assert "b:W3, b:W4, b:W5" in hint
    assert (
        "b:W2" not in hint.split("open steps are")[1]
    )  # an umbrella is passed through


def test_a_single_step_blocker_is_left_alone(tmp_path: Path) -> None:
    # b:W1 waits on one step of its own: it is still the step a:W1 waits for.
    _write(tmp_path, "b", [("W1", "blocked", ["W2"]), ("W2", "ready", [])])
    _write(tmp_path, "a", [("W1", "blocked", ["b:W1"])])
    assert _hints(tmp_path) == {}
