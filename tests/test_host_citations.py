"""nemik:W256: a waypoint blocked on `host:<id>` is held against luthen's host-apply export."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import installed

from nemik.check import survey

EXPORT = {
    "version": 1,
    "as_of": "2026-10-09T06:00:00Z",
    "kinds": {"reload": {"effect": "reload", "restarts": []}},
    "rows": [{"id": "home-mount", "activate": "reload", "after": [], "applied": None}],
}


def _fleet(tmp_path: Path, cited: str) -> Path:
    (tmp_path / "a" / ".claude").mkdir(parents=True)
    state = tmp_path / "a" / ".claude" / "paths-forward.json"
    pf = [*installed.script("mikemol-paths-forward"), "--state", str(state)]
    steps = (
        ["--init"],
        ["--add", "wait for the mount", "--next", "do it"],
        [
            "--update",
            "W1",
            "--status",
            "blocked",
            "--blocked-kind",
            "agent",
            "--blocked-on",
            cited,
        ],
    )
    for args in steps:
        done = subprocess.run(pf + args, capture_output=True, text=True, check=False)
        assert done.returncode == 0, done.stderr
    return tmp_path


def _messages(root: Path) -> list[str]:
    return [msg for _, _, findings in survey(root) for _, _, msg in findings]


def _unresolved(root: Path) -> list[str]:
    return [m for m in _messages(root) if "no resolvable party" in m]


def test_a_cited_row_the_export_holds_is_resolved(tmp_path: Path) -> None:
    root = _fleet(tmp_path, "host:home-mount")
    (root / "host-apply.json").write_text(json.dumps(EXPORT), encoding="utf-8")
    assert _unresolved(root) == []


def test_a_cited_row_the_export_does_not_hold_is_unresolved(tmp_path: Path) -> None:
    root = _fleet(tmp_path, "host:home-mount-typo")
    (root / "host-apply.json").write_text(json.dumps(EXPORT), encoding="utf-8")
    assert len(_unresolved(root)) == 1


def test_without_an_export_the_citation_stays_as_written(tmp_path: Path) -> None:
    # The check cannot read what is not there; it does not guess either way.
    assert _unresolved(_fleet(tmp_path, "host:home-mount")) == []


def test_an_unreadable_export_does_not_break_the_survey(tmp_path: Path) -> None:
    root = _fleet(tmp_path, "host:home-mount")
    (root / "host-apply.json").write_text("{not json", encoding="utf-8")
    assert _unresolved(root) == []
