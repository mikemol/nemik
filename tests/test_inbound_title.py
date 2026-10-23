# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W882: nemik-inbound shows a waiting card's whole title, not its first sixty characters."""

import json
from pathlib import Path

import pytest

from nemik.blocks_cli import main

LONG = (
    "please route the fleet's wait series through the shared emitter, then confirm "
    "the dashboard shows every repo pair, and tell the owner when it does"
)


def _queue(root: Path, repo: str, waypoint: dict[str, object]) -> None:
    queue = root / repo / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    body = {
        "version": 1,
        "project_root": "/x",
        "counter": 2,
        "residue": [],
        "waypoints": [waypoint],
    }
    queue.write_text(json.dumps(body), encoding="utf-8")


def test_a_long_title_is_shown_whole(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The row ends with the title's last word, so a peer reads the ask."""
    _queue(
        tmp_path,
        "a",
        {"symbol": "W1", "title": "t", "status": "ready", "next_bounded_step": "x"},
    )
    _queue(
        tmp_path,
        "b",
        {
            "symbol": "W2",
            "title": LONG,
            "status": "blocked",
            "blocked_on": ["a:W1"],
            "blocked_kind": "agent",
            "next_bounded_step": "x",
        },
    )
    main(["a", "--root", str(tmp_path)])
    assert LONG in capsys.readouterr().out
