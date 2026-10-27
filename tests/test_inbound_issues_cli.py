# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1169: nemik-inbound --issues FILE prints the unclaimed letters, --census the counts."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from nemik.blocks_cli import main

if TYPE_CHECKING:
    import pytest


def _issue(number: int, labels: list[str], state: str = "open") -> dict[str, object]:
    return {
        "number": number,
        "title": f"letter {number}",
        "state": state,
        "body": "please do x",
        "html_url": f"https://example.test/o/r/issues/{number}",
        "labels": [{"name": name} for name in labels],
        "locked": False,
    }


ROWS: list[dict[str, object]] = [
    _issue(1, ["from:linux-sources", "kind:ask", "cites:nemik:W1049"]),
    _issue(2, ["from:linux-sources", "kind:info"], "closed"),
    _issue(3, ["from:mtools", "kind:ask"]),
    _issue(4, ["bug"]),
]


def _saved(tmp_path: Path) -> Path:
    path = tmp_path / "issues.json"
    path.write_text(json.dumps(ROWS))
    return path


def test_the_open_letters_no_waypoint_cites_print_as_unclaimed_rows(
    tmp_path: Path, capsys: "pytest.CaptureFixture[str]"
) -> None:
    """With no queue read every open letter is unclaimed; a queue citing one claims it."""
    saved = _saved(tmp_path)
    main(["--issues", str(saved), "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert [line.split("UNCLAIMED")[0].split()[-1] for line in out.splitlines()] == [
        "https://example.test/o/r/issues/1",
        "https://example.test/o/r/issues/3",
    ]
    assert "ask from linux-sources: letter 1" in out
    queue = tmp_path / "nemik" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    queue.write_text('{"evidence": "nemik:W1049"}')
    main(["nemik", "--issues", str(saved), "--root", str(tmp_path)])
    rows = capsys.readouterr().out
    assert len(rows.splitlines()) == 1
    assert "letter 3" in rows


def test_by_peer_sums_the_kinds_into_one_line_per_sender(
    tmp_path: Path, capsys: "pytest.CaptureFixture[str]"
) -> None:
    """The per-peer grouping linux-sources compares against: n letters, open and closed."""
    argv = ["--issues", str(_saved(tmp_path)), "--census", "--by-peer"]
    main([*argv, "--root", str(tmp_path)])
    assert capsys.readouterr().out.splitlines() == [
        "linux-sources 2 letter(s) open=1 closed=1",
        "mtools 1 letter(s) open=1 closed=0",
    ]


def test_the_census_prints_the_counts_and_no_rows(
    tmp_path: Path, capsys: "pytest.CaptureFixture[str]"
) -> None:
    """One line per sender and kind."""
    main(["--issues", str(_saved(tmp_path)), "--census", "--root", str(tmp_path)])
    assert capsys.readouterr().out.splitlines() == [
        "linux-sources ask open=1 closed=0",
        "linux-sources info open=0 closed=1",
        "mtools ask open=1 closed=0",
    ]
