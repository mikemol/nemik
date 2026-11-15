# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1093: a card blocked on a card that is done in another repo is a Warning.

The rule is nemik's LandedBlockerShape (nemik:W110, W529), a SPARQL constraint over the waitsFor
edges, which cross repos when blocked_on is written `<repo>:W<n>`. These tests hold the cross-repo
case the card names: the host's W54 and W56 sat blocked on luthen:W1653 for eight hours after it
closed.
"""

import json
from typing import TYPE_CHECKING

from nemik.check import survey

if TYPE_CHECKING:
    from pathlib import Path


def _card(symbol: str, status: str, blocked_on: list[str]) -> dict[str, object]:
    return {
        "symbol": symbol,
        "title": "t",
        "status": status,
        "blocked_on": blocked_on,
        "blocked_kind": "agent" if blocked_on else None,
        "enables": [],
        "evidence": "",
    }


def _repo(root: Path, name: str, cards: list[dict[str, object]]) -> None:
    claude = root / name / ".claude"
    claude.mkdir(parents=True)
    state = {
        "version": 1,
        "project_root": str(root / name),
        "counter": 9,
        "residue": [],
        "waypoints": cards,
    }
    (claude / "paths-forward.json").write_text(json.dumps(state), encoding="utf-8")


def _warnings(root: Path, repo: str) -> list[str]:
    for name, _graph, found in survey(root, check=True):
        if name == repo:
            return [msg for sev, _focus, msg in found if sev == "Warning"]
    return []


def test_a_card_blocked_on_a_done_card_in_another_repo_is_a_warning(tmp_path: Path) -> None:
    """a:W1 waits on b:W1, which is done in b's own queue: the block is stale."""
    _repo(tmp_path, "a", [_card("W1", "blocked", ["b:W1"])])
    _repo(tmp_path, "b", [_card("W1", "done", [])])
    said = _warnings(tmp_path, "a")
    assert any("has already landed" in m and "b/W1" in m.replace(":", "/") for m in said), said


def test_a_card_blocked_on_an_open_card_in_another_repo_is_not(tmp_path: Path) -> None:
    """MUTANT: the same block on a card that is still ready draws no landed-blocker warning."""
    _repo(tmp_path, "a", [_card("W1", "blocked", ["b:W1"])])
    _repo(tmp_path, "b", [_card("W1", "ready", [])])
    assert not any("has already landed" in m for m in _warnings(tmp_path, "a"))
