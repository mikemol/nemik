# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W711: nemik-collapse reads a fleet's queues and prints its umbrellas and escapes."""

import json
from pathlib import Path

import pytest

from nemik.check import collapse_main


def _card(symbol: str, waits: list[str], enables: list[str]) -> dict[str, object]:
    """Build one open queue entry.

    Args:
        symbol: Its symbol.
        waits: The cards it is blocked on.
        enables: The cards it enables.

    Returns:
        The entry.

    """
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": "blocked" if waits else "ready",
        "enables": enables,
        "blocked_on": waits,
        "blocked_kind": "agent" if waits else None,
    }


def _fleet(root: Path) -> None:
    """Lay out one repo where two cards wait on the same card, and one edge escapes.

    Args:
        root: The fleet root (the export layout: one queue file per repo).

    """
    queue = {
        "version": 1,
        "counter": 5,
        "project_root": "/fixture/alpha",
        "residue": [],
        "waypoints": [
            _card("W1", [], ["W2", "W3"]),
            _card("W2", ["W1"], []),
            _card("W3", ["W1"], []),
            _card("W4", [], ["W5"]),
            _card("W5", [], []),
        ],
    }
    (root / "alpha").mkdir()
    (root / "alpha" / "paths-forward.json").write_text(json.dumps(queue))


def test_the_fleet_prints_its_umbrella_and_its_escape(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One umbrella under alpha:W1 and one escape, alpha:W4 enabling alpha:W5."""
    _fleet(tmp_path)
    collapse_main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "1 umbrella(s), 1 escape(s)" in out
    assert "2 cards collapse under alpha:W1" in out
    assert "escape: alpha:W4 enables alpha:W5, which does not wait on it" in out
