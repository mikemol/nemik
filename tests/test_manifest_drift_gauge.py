# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W611: nemik_manifest_drift counts done cards whose commits strayed from the manifest."""

from pathlib import Path

import pytest
from rdflib import Graph, Literal

from nemik import history
from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.metrics import drift_lines


def _touched(repo: Path, symbol: str) -> list[str]:
    """Answer as a history where W1 touched one file outside its manifest and W2 touched none.

    Args:
        repo: The repo's directory, unused.
        symbol: The card.

    Returns:
        The files the card's commits touched.

    """
    del repo
    return {"W1": ["src/a.py", "BUILD.bazel"], "W2": ["src/b.py"]}[symbol]


def _graph() -> Graph:
    """Build two done cards with a manifest each.

    Returns:
        The graph.

    """
    g = Graph()
    for symbol, path in (("W1", "src/a.py"), ("W2", "src/b.py")):
        node = waypoint_uri("alpha", symbol)
        g.add((node, OSLC_CM.state, STATE["done"]))
        g.add((node, NEMIK.plannedPath, Literal(path)))
    return g


def _fleet(root: Path, *, with_git: bool) -> None:
    """Lay out one repo with a queue file, and a .git directory when it has history.

    Args:
        root: The fleet root.
        with_git: Whether the repo has a git directory.

    """
    queue = root / "alpha" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    queue.write_text("{}", encoding="utf-8")
    if with_git:
        (root / "alpha" / ".git").mkdir()


def test_a_repo_with_history_counts_its_drifted_cards(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One of the two done cards touched a file its manifest lacked."""
    _fleet(tmp_path, with_git=True)
    monkeypatch.setattr(history, "cited_files", _touched)
    lines = drift_lines(tmp_path, _graph())
    assert 'nemik_manifest_drift{repo="alpha"} 1' in lines


def test_a_repo_with_no_history_gets_no_sample_not_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An export layout has no git; a 0 there would claim every manifest held."""
    _fleet(tmp_path, with_git=False)
    monkeypatch.setattr(history, "cited_files", _touched)
    assert drift_lines(tmp_path, _graph()) == ["# TYPE nemik_manifest_drift gauge"]
