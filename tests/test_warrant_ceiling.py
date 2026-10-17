# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W608: nemik-check warns on a repo whose warrant debt is above its declared ceiling."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.warrantdebt import baseline, findings

PACKAGED_DEBT = 72


def _claiming(tmp_path: Path, repo: str, count: int) -> Graph:
    """Read a queue of cards that claim an operator ruling and carry no warrant.

    Args:
        tmp_path: A scratch directory.
        repo: The repo's name.
        count: How many such cards.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    cards: list[dict[str, object]] = [
        {
            "symbol": f"W{i + 1}",
            "title": "t",
            "status": "ready",
            "next_bounded_step": "per the operator, do x",
        }
        for i in range(count)
    ]
    state: dict[str, object] = {
        "version": 1,
        "project_root": f"/{repo}",
        "counter": count,
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / f"{repo}.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph(repo, path)


def test_a_repo_above_its_ceiling_is_named_and_one_at_it_is_not(tmp_path: Path) -> None:
    """Three claims against a ceiling of two warn; two against two do not; absent means zero."""
    merged = _claiming(tmp_path, "over", 3)
    merged += _claiming(tmp_path, "at", 2)
    merged += _claiming(tmp_path, "new", 1)
    said = findings(merged, {"over": 2, "at": 2})
    assert sorted(said) == ["new", "over"]
    assert "3 open cards" in said["over"]


def test_the_packaged_ceilings_are_the_counted_debt() -> None:
    """The shipped table sums to the 72 cards first counted, and holds no negative number."""
    ceilings = baseline()
    assert sum(ceilings.values()) == PACKAGED_DEBT
    assert min(ceilings.values()) >= 0
