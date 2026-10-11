"""nemik:W331: nemik-check warns on each card in a dependency deadlock the operator cannot break."""

from __future__ import annotations

import json
from pathlib import Path

from nemik.check import survey


def _root(tmp_path: Path, kinds: tuple[str, str]) -> Path:
    queue = tmp_path / "a" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    waypoints = [
        {
            "symbol": "W1",
            "title": "one",
            "status": "blocked",
            "blocked_on": ["W2"],
            "blocked_kind": kinds[0],
            "next_bounded_step": "x",
        },
        {
            "symbol": "W2",
            "title": "two",
            "status": "blocked",
            "blocked_on": ["W1"],
            "blocked_kind": kinds[1],
            "next_bounded_step": "x",
        },
    ]
    queue.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": "/x",
                "counter": 2,
                "residue": [],
                "waypoints": waypoints,
            }
        )
    )
    return tmp_path


def _cycle_warnings(root: Path) -> list[tuple[str, str]]:
    return [
        (sym, msg)
        for _, _, findings in survey(root)
        for sev, sym, msg in findings
        if sev == "Warning" and "dependency cycle" in msg
    ]


def test_each_card_of_an_agent_deadlock_is_warned() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        found = _cycle_warnings(_root(Path(tmp), ("agent", "agent")))
    assert sorted(sym for sym, _ in found) == ["W1", "W2"]
    assert "a:W2" in dict(found)["W1"]


def test_a_cycle_with_an_operator_block_is_left_to_the_operator() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        assert _cycle_warnings(_root(Path(tmp), ("agent", "human"))) == []
