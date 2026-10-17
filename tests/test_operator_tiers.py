# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W600: nemik-operator lists a category's asks grouped by the repo's burn-down tier."""

import json
from pathlib import Path

import pytest
from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.blocks_cli import operator_main
from nemik.tiers import of_cite


def _asking(tmp_path: Path, repo: str) -> Graph:
    """Read a queue whose one card waits on the operator for a decision.

    Args:
        tmp_path: A scratch directory.
        repo: The repo's name.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    card: dict[str, object] = {
        "symbol": "W1",
        "title": f"{repo} asks",
        "status": "blocked",
        "blocked_on": ["operator: decide which way"],
        "blocked_kind": "human",
        "next_bounded_step": "x",
    }
    state: dict[str, object] = {
        "version": 1,
        "project_root": f"/{repo}",
        "counter": 1,
        "residue": residue,
        "waypoints": [card],
    }
    path = tmp_path / f"{repo}.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph(repo, path)


def test_of_cite_names_the_tier_of_the_repo() -> None:
    """A cited repo reads its declared tier; one not declared is unlisted."""
    declared = {"nemik": "now"}
    assert of_cite("nemik:W5", declared) == "now"
    assert of_cite("gone:W1", declared) == "unlisted"


def test_asks_list_the_now_tier_before_a_later_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repo in only-when-blocking sorts first by name; the now-tier repo still prints first."""
    merged = _asking(tmp_path, "aeternum")
    merged += _asking(tmp_path, "nemik")
    operator_main([], merged)
    out = capsys.readouterr().out
    assert out.index("nemik:W1") < out.index("aeternum:W1")
