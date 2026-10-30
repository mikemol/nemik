# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1281: nemik-wake --series-lines prints one liveness line per repo from luthen's series."""

import json
import time
from pathlib import Path

import pytest
from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.luthenseries import parse
from nemik.wake import main, series_lines

AS_OF = 1_793_000_000
STAMP = "2026-10-26T07:33:20Z"


def _text(repos: dict[str, object], as_of: int = AS_OF) -> str:
    body = {"version": 1, "as_of": as_of, "liveness": repos, "tokens": []}
    return json.dumps(body)


def test_a_measured_repo_prints_its_verdict_and_the_snapshots_instant() -> None:
    """Each line is repo, verdict, as_of, and every line carries the same as_of."""
    repos: dict[str, object] = {
        "nemik": {"verdict": "ok", "last_tick": AS_OF - 5},
        "linux-sources": {"verdict": "dormant"},
    }
    series = parse(_text(repos), AS_OF + 1, 900)
    assert series_lines(series, []) == [
        f"linux-sources dormant {STAMP}",
        f"nemik ok {STAMP}",
    ]


def test_a_repo_with_no_series_reads_no_sample_never_ok_or_dormant() -> None:
    """A repo the graph knows and the series does not, or one with an empty verdict."""
    repos: dict[str, object] = {"nemik": {"verdict": "ok"}, "quiet": {"verdict": ""}}
    series = parse(_text(repos), AS_OF, 900)
    assert series_lines(series, ["nemik", "ghost"]) == [
        f"ghost no sample {STAMP}",
        f"nemik ok {STAMP}",
        f"quiet no sample {STAMP}",
    ]


def _graph(tmp_path: Path) -> Graph:
    queue = tmp_path / "q.json"
    payload: dict[str, object] = {
        "version": 1,
        "project_root": "/x",
        "counter": 1,
        "residue": [],
        "waypoints": [{"symbol": "W1", "title": "t", "status": "ready"}],
    }
    queue.write_text(json.dumps(payload))
    return queue_graph("life", queue)


def test_the_mode_prints_the_lines_from_the_snapshot_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The graph's workstream with no series line prints no sample beside the series' own."""
    snapshot = tmp_path / "luthen-series.json"
    repos: dict[str, object] = {"nemik": {"verdict": "ok"}}
    snapshot.write_text(_text(repos, int(time.time())))
    main(["--series-lines", "--series", str(snapshot)], _graph(tmp_path))
    lines = capsys.readouterr().out.splitlines()
    assert [ln.split()[:2] for ln in lines] == [["life", "no"], ["nemik", "ok"]]
    assert lines[0].split()[1:3] == ["no", "sample"]


def test_a_snapshot_older_than_the_bound_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A stopped producer must not read as live: nothing on stdout, the reason on stderr, exit 1."""
    snapshot = tmp_path / "luthen-series.json"
    repos: dict[str, object] = {"nemik": {"verdict": "ok"}}
    snapshot.write_text(_text(repos))
    with pytest.raises(SystemExit) as refused:
        main(
            ["--series-lines", "--series", str(snapshot), "--series-max-age", "60"],
            _graph(tmp_path),
        )
    captured = capsys.readouterr()
    assert refused.value.code == 1
    assert not captured.out
    assert "series: as_of is" in captured.err


def test_a_missing_snapshot_is_refused_the_same_way(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No file is a refusal with a reason, not an empty success."""
    with pytest.raises(SystemExit) as refused:
        main(
            ["--series-lines", "--series", str(tmp_path / "absent.json")],
            _graph(tmp_path),
        )
    assert refused.value.code == 1
    assert capsys.readouterr().err.startswith("series: ")
