# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W695: nemik-check --integrity reports every repo, or only the one named with --repo."""

import json
from pathlib import Path

import pytest

from nemik.check import integrity_report


def _card(symbol: str, enables: list[str]) -> dict[str, object]:
    """Build one open card.

    Args:
        symbol: Its symbol.
        enables: The cards it enables.

    Returns:
        The queue entry.

    """
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": "ready",
        "enables": enables,
        "blocked_on": [],
        "blocked_kind": None,
    }


def _fleet(root: Path) -> None:
    """Lay out two repos, each with one enables edge whose target does not wait on its source.

    Args:
        root: The fleet root (the export layout: one queue file per repo).

    """
    for repo in ("alpha", "beta"):
        queue = {
            "version": 1,
            "counter": 2,
            "project_root": f"/fixture/{repo}",
            "residue": [],
            "waypoints": [_card("W1", ["W2"]), _card("W2", [])],
        }
        (root / repo).mkdir()
        (root / repo / "paths-forward.json").write_text(json.dumps(queue))


def test_every_repo_is_reported_without_a_repo_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both repos' findings and counts print."""
    _fleet(tmp_path)
    assert integrity_report(tmp_path) == 0
    out = capsys.readouterr().out
    assert "alpha: 1 finding(s)" in out
    assert "beta: 1 finding(s)" in out


def test_only_the_named_repo_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--repo alpha prints alpha's findings and its count, and nothing of beta."""
    _fleet(tmp_path)
    assert integrity_report(tmp_path, "alpha") == 0
    out = capsys.readouterr().out
    assert "alpha: 1 finding(s)" in out
    assert "alpha:W1: enables alpha:W2" in out
    assert "beta" not in out


def test_a_repo_with_no_findings_prints_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unknown repo name has no findings, so the report is empty."""
    _fleet(tmp_path)
    assert integrity_report(tmp_path, "gamma") == 0
    assert not capsys.readouterr().out
