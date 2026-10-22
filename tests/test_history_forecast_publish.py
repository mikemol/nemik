# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W855: nemik-history --forecast --publish writes a document nemik-serve serves."""

from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

import pytest

from nemik.cardevents import Event
from nemik.histdocs import decode
from nemik.history import main
from nemik.serve import history_response

ROW = ["alpha:W1", "2026-10-22T10:00:00+00:00", "+1", "0.5"]


def _fake_backfill(
    _repo: str, _repo_dir: Path, _since: str | None = None
) -> list[Event]:
    """Stand for the walk over a repo's committed queue.

    Returns:
        No events: the forecast rows are faked too.

    """
    return []


def _fake_rows(_events: list[Event], _moment: str) -> list[list[str]]:
    """Stand for the forecast over the open cards.

    Returns:
        One shingle row.

    """
    return [ROW]


def _fleet(root: Path) -> None:
    """Make one workstream, `alpha`, with a queue file."""
    state = root / "alpha" / ".claude" / "paths-forward.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}", encoding="utf-8")


def test_forecast_publishes_its_rows_and_the_route_serves_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shingle row reaches the document, then the route."""
    monkeypatch.setattr("nemik.history.backfill", _fake_backfill)
    monkeypatch.setattr("nemik.history.forecast_rows", _fake_rows)
    _fleet(tmp_path / "fleet")
    out = tmp_path / "docs"
    argv = ["alpha", "--root", str(tmp_path / "fleet"), "--from", "2026-10-15"]
    assert main([*argv, "--forecast", "--publish", str(out)]) == 0
    as_of, body = decode((out / "forecast.json").read_text(encoding="utf-8"))
    assert as_of
    assert '"alpha:W1"' in body
    code, _, wrapped = history_response(
        out, "/history/forecast.json", datetime.now(UTC)
    )
    assert code == HTTPStatus.OK
    assert '"mode": "forecast"' in wrapped.decode("utf-8")


def test_forecast_without_publish_still_prints_a_row_a_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No --publish and no --json: a tab-separated row, and no document."""
    monkeypatch.setattr("nemik.history.backfill", _fake_backfill)
    monkeypatch.setattr("nemik.history.forecast_rows", _fake_rows)
    _fleet(tmp_path)
    argv = ["alpha", "--root", str(tmp_path), "--from", "2026-10-15", "--forecast"]
    assert main(argv) == 0
    assert capsys.readouterr().out == "\t".join(ROW) + "\n"
    assert not list(tmp_path.glob("**/forecast.json"))
