"""nemik:W279: a waypoint that cites a letter file as evidence must name one that exists."""

from __future__ import annotations

import json
from pathlib import Path

from nemik.check import survey


def _root(tmp_path: Path, evidence: str) -> Path:
    queue = tmp_path / "a" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    queue.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": "/x",
                "counter": 1,
                "residue": [],
                "waypoints": [
                    {
                        "symbol": "W1",
                        "title": "t",
                        "status": "ready",
                        "evidence": evidence,
                        "next_bounded_step": "do it",
                    }
                ],
            }
        )
    )
    (tmp_path / "a" / "inbox").mkdir()
    return tmp_path


def _letter_findings(root: Path) -> list[str]:
    return [
        msg
        for _, _, findings in survey(root)
        for _, _, msg in findings
        if "cites the letter" in msg
    ]


def test_a_cited_letter_that_does_not_exist_is_a_warning(tmp_path: Path) -> None:
    root = _root(tmp_path, "Letter: a/inbox/gone.md")
    (found,) = _letter_findings(root)
    assert "a/inbox/gone.md" in found


def test_a_cited_letter_that_exists_or_was_archived_is_fine(tmp_path: Path) -> None:
    root = _root(tmp_path, "Letters: a/inbox/here.md and a/inbox/old.md")
    (root / "a" / "inbox" / "here.md").write_text("x")
    (root / "a" / "inbox" / "archive").mkdir()
    (root / "a" / "inbox" / "archive" / "old.md").write_text("x")
    assert _letter_findings(root) == []


def test_a_root_with_no_inbox_is_not_asked(tmp_path: Path) -> None:
    root = _root(tmp_path, "Letter: a/inbox/gone.md")
    (root / "a" / "inbox").rmdir()
    assert _letter_findings(root) == []
