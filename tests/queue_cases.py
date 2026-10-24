# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W973: builders for small fixture queues, shared by the tests that read them as graphs."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph

KNOWN = frozenset({"alpha", "beta"})


def make_card(
    symbol: str,
    status: str,
    waits: list[str],
    enables: list[str],
    caused_by: str = "",
) -> dict[str, object]:
    """Build one queue entry.

    Returns:
        The entry.

    """
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": status,
        "enables": enables,
        "blocked_on": waits,
        "blocked_kind": "agent" if waits else None,
        "caused_by": caused_by,
    }


def write_queue(path: Path, repo: str, cards: list[dict[str, object]]) -> Graph:
    """Write a queue and read it as a graph.

    Returns:
        The repo's graph.

    """
    body: dict[str, object] = {
        "version": 1,
        "counter": 20,
        "project_root": f"/fixture/{repo}",
        "residue": [],
        "waypoints": cards,
    }
    path.write_text(json.dumps(body), encoding="utf-8")
    return queue_graph(repo, path, KNOWN)
