# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W613: --propose drafts a manifest from the step, the touches and the commits."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.stackable import draft, propose, resolve

WIDE_FILES = 8
KNOWN = {
    "src/nemik/a.py",
    "src/nemik/b.py",
    "tests/test_a.py",
    "docs/x.md",
    "tests/b.py",
}


def _queue(tmp_path: Path) -> Graph:
    """Read a queue whose W1 names a file in its step and declares another as a touch.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    cards: list[dict[str, object]] = [
        {
            "symbol": "W1",
            "title": "t",
            "status": "ready",
            "next_bounded_step": "edit a.py and nothing else",
            "touches": ["file:docs/x.md!w"],
        },
        {"symbol": "W2", "title": "t", "status": "ready", "manifest": ["a.py"]},
        {"symbol": "W3", "title": "t", "status": "ready"},
    ]
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/r",
        "counter": len(cards),
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / "r.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("r", path)


def test_a_bare_name_resolves_only_when_one_tracked_path_ends_in_it() -> None:
    """A full path is kept; a bare name needs exactly one tracked match; b.py is ambiguous."""
    assert resolve("src/nemik/a.py", KNOWN) == "src/nemik/a.py"
    assert resolve("a.py", KNOWN) == "src/nemik/a.py"
    assert resolve("b.py", KNOWN) is None
    assert resolve("gone.py", KNOWN) is None


def test_the_draft_joins_the_step_the_touches_and_the_commits(tmp_path: Path) -> None:
    """The step's a.py, the declared docs/x.md and a cited test all land, queue files do not."""
    g = _queue(tmp_path)
    cited = ["tests/test_a.py", ".claude/paths-forward.json"]
    files, sources = draft(g, "r", "W1", cited, KNOWN)
    assert files == ["docs/x.md", "src/nemik/a.py", "tests/test_a.py"]
    assert sources == ["next-step", "touches", "commits"]


def test_a_draft_from_past_commits_alone_is_flagged_when_wide(tmp_path: Path) -> None:
    """mtools-ad: many files from the citing commits alone is wider than the card; say so."""
    g = _queue(tmp_path)
    many = {f"src/nemik/m{i}.py" for i in range(WIDE_FILES)}
    ranked: list[dict[str, object]] = [{"symbol": "W3"}]
    lines = propose(g, "r", ranked, {"W3": sorted(many)}, many)
    assert "WIDE" in lines[0]
    few = propose(g, "r", ranked, {"W3": ["src/nemik/m0.py"]}, many)
    assert "WIDE" not in few[0]


def test_propose_skips_a_card_that_already_has_a_manifest(tmp_path: Path) -> None:
    """W2 is declared, so only W1 and W3 get a line; W3 has nothing to propose."""
    g = _queue(tmp_path)
    ranked: list[dict[str, object]] = [{"symbol": s} for s in ("W1", "W2", "W3")]
    lines = propose(g, "r", ranked, {}, KNOWN)
    assert [line.split(":")[0] for line in lines] == ["W1", "W3"]
    assert "--manifest docs/x.md src/nemik/a.py" in lines[0]
    assert "nothing to propose" in lines[1]
