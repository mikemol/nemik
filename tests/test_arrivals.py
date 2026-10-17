# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W609: nemik_cards_arrived_24h counts the cards issued in the last day, per repo."""

import json
from datetime import UTC, datetime
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.metrics import arrival_lines, render

NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=UTC)


def _queue(tmp_path: Path, repo: str, issued: list[str]) -> Graph:
    """Read a queue with one ready card per issue time.

    Args:
        tmp_path: A scratch directory.
        repo: The repo's name.
        issued: The cards' issued_at texts.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    cards: list[dict[str, object]] = [
        {
            "symbol": f"W{i + 1}",
            "title": "t",
            "status": "ready",
            "issued_at": at,
            "next_bounded_step": "x",
        }
        for i, at in enumerate(issued)
    ]
    state: dict[str, object] = {
        "version": 1,
        "project_root": f"/{repo}",
        "counter": len(cards),
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / f"{repo}.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph(repo, path)


def test_only_cards_issued_within_a_day_count(tmp_path: Path) -> None:
    """Two recent cards and one old one: the repo reads 2; a quiet repo reads 0."""
    merged = _queue(
        tmp_path,
        "nemik",
        ["2026-10-16T11:00:00Z", "2026-10-15T13:00:00Z", "2026-10-14T12:00:00Z"],
    )
    merged += _queue(tmp_path, "quiet", ["2026-10-01T00:00:00Z"])
    lines = arrival_lines(merged, NOW)
    assert 'nemik_cards_arrived_24h{repo="nemik"} 2' in lines
    assert 'nemik_cards_arrived_24h{repo="quiet"} 0' in lines


def test_the_family_prints_with_its_help_line(tmp_path: Path) -> None:
    """The family has HELP text, so the exposition stays valid."""
    merged = _queue(tmp_path, "nemik", ["2026-10-16T11:00:00Z"])
    text = render(arrival_lines(merged, NOW), None)
    assert text.startswith("# HELP nemik_cards_arrived_24h ")
