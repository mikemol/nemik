# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W858: nemik-history --density --publish writes a document nemik-serve serves."""

from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

import pytest

from nemik.histdocs import decode
from nemik.history import main
from nemik.serve import history_response

COMMITS = (
    "2026-10-20T10:00:00+00:00\n2026-10-21T10:00:00+00:00\n2026-10-22T10:00:00+00:00\n"
)


def _fake_git(_repo: Path, *_args: str) -> str:
    """Stand for `git log` over the queue file.

    Returns:
        Three commit times, a day apart.

    """
    return COMMITS


def _fleet(root: Path) -> None:
    """Make one workstream, `alpha`, with a queue file and no ledger."""
    state = root / "alpha" / ".claude" / "paths-forward.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}", encoding="utf-8")


def test_density_publishes_its_rows_and_the_route_serves_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The commit count and the longest gap reach the document, then the route."""
    monkeypatch.setattr("nemik.history._git", _fake_git)
    _fleet(tmp_path / "fleet")
    out = tmp_path / "docs"
    argv = ["alpha", "--root", str(tmp_path / "fleet"), "--from", "2026-10-15"]
    assert main([*argv, "--density", "--publish", str(out)]) == 0
    as_of, body = decode((out / "density.json").read_text(encoding="utf-8"))
    assert as_of
    assert '"commits": 3' in body
    assert '"longest_gap_hours": 24.0' in body
    code, _, wrapped = history_response(out, "/history/density.json", datetime.now(UTC))
    assert code == HTTPStatus.OK
    assert '"mode": "density"' in wrapped.decode("utf-8")


def test_density_without_publish_still_prints_its_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No --publish and no --json: the text line, and no document."""
    monkeypatch.setattr("nemik.history._git", _fake_git)
    _fleet(tmp_path)
    argv = ["alpha", "--root", str(tmp_path), "--from", "2026-10-15", "--density"]
    assert main(argv) == 0
    assert "alpha: 3 commits" in capsys.readouterr().out
    assert not list(tmp_path.glob("**/density.json"))
