# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W356: a card waiting on another repo past the declared SLA is a Warning on the blocker."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from nemik.check import survey


def _write(root: Path, repo: str, waypoints: list[dict[str, object]]) -> None:
    queue = root / repo / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    payload: dict[str, object] = {
        "version": 1,
        "project_root": "/x",
        "counter": len(waypoints),
        "residue": [],
        "waypoints": waypoints,
    }
    queue.write_text(json.dumps(payload))


def _late(ticks: int, blocker_kind: str | None = None) -> list[tuple[str, str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        blocker: dict[str, object] = {
            "symbol": "W1",
            "title": "b",
            "status": "ready",
            "next_bounded_step": "x",
        }
        if blocker_kind:
            blocker |= {
                "status": "blocked",
                "blocked_on": ["operator: decide x or y"],
                "blocked_kind": blocker_kind,
            }
        _write(root, "b", [blocker])
        _write(
            root,
            "a",
            [
                {
                    "symbol": "W1",
                    "title": "a",
                    "status": "blocked",
                    "blocked_on": ["b:W1"],
                    "blocked_kind": "agent",
                    "ticks_blocked": ticks,
                    "next_bounded_step": "x",
                }
            ],
        )
        return [
            (repo, sym, msg)
            for repo, _, findings in survey(root)
            for sev, sym, msg in findings
            if sev == "Warning" and "loop ticks (SLA" in msg
        ]


def test_past_the_sla_the_blockers_card_is_warned() -> None:
    """Past the sla the blockers card is warned."""
    found = _late(49)
    assert found == [
        (
            "b",
            "W1",
            (
                "has kept a:W1 waiting 49 loop ticks (SLA 48): answer it, re-scope it, "
                "or tell a why it waits"
            ),
        )
    ]


def test_within_the_sla_or_blocked_on_the_operator_nothing_is_warned() -> None:
    """Within the sla or blocked on the operator nothing is warned."""
    assert _late(48) == []
    assert _late(60, blocker_kind="human") == []
