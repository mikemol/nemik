# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1167: the server names the term that bounded each repo's round from the graph."""

import json
from pathlib import Path

from nemik.adapter import queue_graph
from nemik.roundcli import NO_LANDINGS, bindings_of
from nemik.serve import round_bindings


def _card(symbol: str, status: str, files: list[str]) -> dict[str, object]:
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": status,
        "enables": [],
        "blocked_on": [],
        "blocked_kind": None,
        "ticks_blocked": 0,
        "manifest": files,
    }


def _binding(
    tmp_path: Path, repo: str, cards: list[dict[str, object]]
) -> dict[str, str]:
    body: dict[str, object] = {
        "version": 1,
        "counter": 9,
        "project_root": "/x",
        "residue": [],
        "waypoints": cards,
    }
    path = tmp_path / f"{repo}.json"
    path.write_text(json.dumps(body))
    nodes: list[dict[str, object]] = [
        {"repo": repo, "symbol": c["symbol"], "state": "ready"} for c in cards
    ]
    graph = queue_graph(repo, path, frozenset({repo}))
    return round_bindings(graph, nodes, tmp_path / "landings.json")


def test_the_binding_term_is_read_from_each_repos_ready_manifests(
    tmp_path: Path,
) -> None:
    """Four ready cards on disjoint files outrun the floor of three: supply binds. Two do not."""
    wide = [_card(f"W{n}", "ready", [f"f{n}.py"]) for n in range(1, 5)]
    narrow = [_card(f"W{n}", "ready", [f"g{n}.py"]) for n in range(1, 3)]
    assert _binding(tmp_path, "wide", wide) == {"wide": "supply"}
    assert _binding(tmp_path, "narrow", narrow) == {"narrow": "floor"}


def test_a_working_card_keeps_its_files_busy_and_no_repo_means_no_term() -> None:
    """A working card's files are busy, so a ready card on them cannot stack beside it."""
    rows: dict[str, list[dict[str, object]]] = {
        "r": [
            {"state": "working", "manifest": ["a.py"]},
            {"state": "ready", "manifest": ["a.py"]},
        ]
    }
    assert bindings_of(rows, NO_LANDINGS) == {"r": "floor"}
    assert bindings_of({}, NO_LANDINGS) == {}
