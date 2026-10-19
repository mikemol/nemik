# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W710: nemik-check tells a repo how many blocked cards wait behind one of its cards."""

import json
from pathlib import Path

from nemik.adapter import queue_graph
from nemik.check import Finding, add_umbrella_infos


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


def _infos(root: Path, cards: list[dict[str, object]]) -> dict[str, list[Finding]]:
    """Write one repo with the given cards and run the umbrella check.

    Args:
        root: A scratch directory.
        cards: The repo's queue entries.

    Returns:
        The findings the check added, by repo.

    """
    body: dict[str, object] = {
        "version": 1,
        "counter": 9,
        "project_root": "/fixture/alpha",
        "residue": [],
        "waypoints": cards,
    }
    path = root / "paths-forward.json"
    path.write_text(json.dumps(body))
    found: dict[str, list[Finding]] = {}
    add_umbrella_infos(queue_graph("alpha", path), found)
    return found


def test_two_cards_behind_one_are_one_umbrella(tmp_path: Path) -> None:
    """The repo gets one Info naming the umbrella count, the cards held and the largest."""
    found = _infos(
        tmp_path,
        [
            _card("W1", [], ["W2", "W3"]),
            _card("W2", ["W1"], []),
            _card("W3", ["W1"], []),
        ],
    )
    assert [sev for sev, _, _ in found["alpha"]] == ["Info"]
    message = found["alpha"][0][2]
    assert "1 umbrella(s) hold 2 blocked cards" in message
    assert "largest is alpha:W1" in message


def test_no_shared_blocker_means_no_info(tmp_path: Path) -> None:
    """Independent cards form no umbrella, so nothing is said."""
    assert not _infos(tmp_path, [_card("W1", [], []), _card("W2", [], [])])
