# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W898: nemik-check --warnings --repo R prints that repo's Warning rows and nothing else."""

import json
from pathlib import Path

import pytest

from nemik.check import warnings_report


def _repo(root: Path, name: str) -> None:
    """Write a queue with one card that draws a Warning and one that draws an Info.

    Args:
        root: A scratch directory.
        name: The repo.

    """
    queue = root / name / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    waits: dict[str, object] = {
        "symbol": "W1",
        "title": "waits on the operator",
        "status": "blocked",
        "blocked_on": ["operator"],
        "blocked_kind": "human",
        "next_bounded_step": "x",
    }
    ready: dict[str, object] = {
        "symbol": "W2",
        "title": "ready with no manifest",
        "status": "ready",
        "next_bounded_step": "x",
    }
    body: dict[str, object] = {
        "version": 1,
        "project_root": f"/{name}",
        "counter": 2,
        "residue": [],
        "waypoints": [waits, ready],
    }
    queue.write_text(json.dumps(body), encoding="utf-8")


def test_one_repos_warnings_are_printed_and_the_rest_are_not(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Repo a's Warning row prints under its header; Info rows and repo b do not."""
    _repo(tmp_path, "a")
    _repo(tmp_path, "b")
    assert warnings_report(tmp_path, "a") == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].split() == ["OK", "a"]
    assert "Warning" in out
    assert "Info" not in out
    assert not any(line.split()[:2] == ["OK", "b"] for line in out.splitlines())


def test_without_a_repo_every_repos_header_prints(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no repo named, each repo gets its header and its Warning rows."""
    _repo(tmp_path, "a")
    _repo(tmp_path, "b")
    warnings_report(tmp_path, None)
    headers = [
        line.split()[1]
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("OK")
    ]
    assert headers == ["a", "b"]
