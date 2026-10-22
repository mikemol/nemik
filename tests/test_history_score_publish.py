# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W856: nemik-history --score --publish writes a document nemik-serve serves."""

from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

import pytest

from nemik.cardevents import Event
from nemik.histdocs import decode
from nemik.history import main
from nemik.serve import history_response

REPORT = {
    "+1": {
        "n": 4.0,
        "brier": 0.25,
        "persistence": 0.3,
        "skill_persistence": 0.1,
        "climatology": 0.4,
        "skill_climatology": 0.2,
    }
}


def _fake_backfill(
    _repo: str, _repo_dir: Path, _since: str | None = None
) -> list[Event]:
    """Stand for the walk over a repo's committed queue.

    Returns:
        No events: the report is faked too.

    """
    return []


def _fake_report(*_args: object) -> dict[str, dict[str, float]]:
    """Stand for the Brier report over a stored shingle.

    Returns:
        One lead with its count and score.

    """
    return REPORT


def _fleet(root: Path) -> None:
    """Make one workstream, `alpha`, with a queue file."""
    state = root / "alpha" / ".claude" / "paths-forward.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}", encoding="utf-8")


def test_score_publishes_its_report_and_the_route_serves_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The per-lead score reaches the document, then the route."""
    monkeypatch.setattr("nemik.history.backfill", _fake_backfill)
    monkeypatch.setattr("nemik.history.score_report", _fake_report)
    _fleet(tmp_path / "fleet")
    shingle = tmp_path / "shingle.tsv"
    shingle.write_text("", encoding="utf-8")
    out = tmp_path / "docs"
    argv = ["alpha", "--root", str(tmp_path / "fleet"), "--from", "2026-10-15"]
    assert main([*argv, "--score", str(shingle), "--publish", str(out)]) == 0
    as_of, body = decode((out / "score.json").read_text(encoding="utf-8"))
    assert as_of
    assert '"brier": 0.25' in body
    code, _, wrapped = history_response(out, "/history/score.json", datetime.now(UTC))
    assert code == HTTPStatus.OK
    assert '"mode": "score"' in wrapped.decode("utf-8")


def test_score_without_publish_still_prints_a_line_per_lead(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No --publish and no --json: the lead's text line, and no document."""
    monkeypatch.setattr("nemik.history.backfill", _fake_backfill)
    monkeypatch.setattr("nemik.history.score_report", _fake_report)
    _fleet(tmp_path)
    shingle = tmp_path / "shingle.tsv"
    shingle.write_text("", encoding="utf-8")
    argv = ["alpha", "--root", str(tmp_path), "--from", "2026-10-15"]
    assert main([*argv, "--score", str(shingle)]) == 0
    assert capsys.readouterr().out.startswith("+1\tn 4")
    assert not list(tmp_path.glob("**/score.json"))
