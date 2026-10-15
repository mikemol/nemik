# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W348: a repo with more needs-you operator asks than the declared cap gets one Warning."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from nemik.check import survey


def _root(tmp: Path, asks: int) -> Path:
    queue = tmp / "a" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    waypoints = [
        {
            "symbol": f"W{i}",
            "title": f"ask {i}",
            "status": "blocked",
            "blocked_on": [f"operator: decide whether to do thing {i} or not"],
            "blocked_kind": "human",
            "next_bounded_step": "x",
            "issued_at": f"2026-10-{i:02d}T00:00:00Z",
        }
        for i in range(1, asks + 1)
    ]
    queue.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": "/x",
                "counter": asks,
                "residue": [],
                "waypoints": waypoints,
            }
        )
    )
    return tmp


def _saturation(root: Path) -> list[str]:
    return [
        msg
        for _, _, findings in survey(root)
        for sev, sym, msg in findings
        if sev == "Warning" and sym == "--" and "needs-you operator asks" in msg
    ]


def test_more_asks_than_the_cap_is_one_warning_naming_the_oldest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        found = _saturation(_root(Path(tmp), 11))
    assert len(found) == 1
    assert found[0].startswith("11 needs-you operator asks are open (cap 10")
    assert "oldest issued 2026-10-01" in found[0]


def test_at_the_cap_there_is_no_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        assert _saturation(_root(Path(tmp), 10)) == []
