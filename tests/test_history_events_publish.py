# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W857: nemik-history --events --publish writes a document nemik-serve serves."""

from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

import pytest

from nemik.cardevents import Event
from nemik.histdocs import decode
from nemik.history import main
from nemik.serve import history_response

EVENT: Event = (
    "alpha:W1",
    "2026-10-21T10:00:00Z",
    "status",
    "ready",
    "done",
    "abc1234",
)


def _fake_backfill(
    _repo: str, _repo_dir: Path, _since: str | None = None
) -> list[Event]:
    """Stand for the walk over a repo's committed queue.

    Returns:
        One event.

    """
    return [EVENT]


def _fleet(root: Path) -> None:
    """Make one workstream, `alpha`, with a queue file."""
    state = root / "alpha" / ".claude" / "paths-forward.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}", encoding="utf-8")


def test_events_publish_their_rows_and_the_route_serves_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The event reaches the document, then the route."""
    monkeypatch.setattr("nemik.history.backfill", _fake_backfill)
    _fleet(tmp_path / "fleet")
    out = tmp_path / "docs"
    argv = ["alpha", "--root", str(tmp_path / "fleet"), "--from", "2026-10-15"]
    assert main([*argv, "--events", "--publish", str(out)]) == 0
    as_of, body = decode((out / "events.json").read_text(encoding="utf-8"))
    assert as_of
    assert '"alpha:W1"' in body
    assert '"abc1234"' in body
    code, _, wrapped = history_response(out, "/history/events.json", datetime.now(UTC))
    assert code == HTTPStatus.OK
    assert '"mode": "events"' in wrapped.decode("utf-8")


def test_events_without_publish_still_print_a_line_each(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No --publish and no --json: a tab-separated line, and no document."""
    monkeypatch.setattr("nemik.history.backfill", _fake_backfill)
    _fleet(tmp_path)
    argv = ["alpha", "--root", str(tmp_path), "--from", "2026-10-15", "--events"]
    assert main(argv) == 0
    assert capsys.readouterr().out == "\t".join(EVENT) + "\n"
    assert not list(tmp_path.glob("**/events.json"))
