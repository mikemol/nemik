# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W600: the fleet ranking puts a more urgent repo's cards first."""

import json
from pathlib import Path

import pytest
from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.rank import load_composition, main


def _queue(tmp_path: Path, repo: str, symbols: list[str]) -> Graph:
    """Read a queue of ready cards.

    Args:
        tmp_path: A scratch directory.
        repo: The repo's name.
        symbols: The ready cards' symbols.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    cards: list[dict[str, object]] = [
        {"symbol": s, "title": s, "status": "ready", "next_bounded_step": "x"}
        for s in symbols
    ]
    state: dict[str, object] = {
        "version": 1,
        "project_root": f"/{repo}",
        "counter": 9,
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / f"{repo}.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph(repo, path)


def test_the_packaged_composition_is_unchanged_per_repo() -> None:
    """The tier orders only the cross-repo pool, so a per-repo composition has no tier tier."""
    assert ("tier",) not in load_composition().tiers


def test_the_fleet_orders_by_tier_before_symbol(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Substrate (later) W1 would win on its lower symbol; nemik (now) W5 wins on its tier."""
    merged = _queue(tmp_path, "substrate", ["W1"])
    merged += _queue(tmp_path, "nemik", ["W5"])
    main(["--all"], merged)
    out = capsys.readouterr().out
    assert out.index("nemik:W5") < out.index("substrate:W1")
