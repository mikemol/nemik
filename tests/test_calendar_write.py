"""nemik:W199 (life's ask): nemik-calendar-write ties calendars.toml, the queues and the helper."""

import json
from pathlib import Path

import pytest
from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.calwrite import main


def _fleet(tmp_path: Path) -> Graph:
    """life with two open dated waypoints, one done, one undated."""
    path = tmp_path / "life.json"
    waypoints = [
        {"symbol": "W9", "title": "cpr", "status": "ready", "due": "20261001T220000Z"},
        {
            "symbol": "W30",
            "title": "drill",
            "status": "ready",
            "dtstart": "TZID=America/Detroit:20261005T180000",
        },
        {"symbol": "W1", "title": "closed", "status": "done", "due": "20261001"},
        {"symbol": "W5", "title": "undated", "status": "ready"},
    ]
    queue = {"version": 1, "project_root": "/x", "counter": 4, "residue": []}
    path.write_text(json.dumps({**queue, "waypoints": waypoints}))
    return queue_graph("life", path)


def _stand_in(tmp_path: Path, code: int = 0) -> Path:
    """A stand-in for nemik-akonadi-tasks: echoes its arguments, counts the events on stdin."""
    helper = tmp_path / "helper"
    helper.write_text(
        f'#!/bin/sh\nn=$(grep -c BEGIN:VEVENT)\necho "ARGS $* EVENTS $n"\nexit {code}\n'
    )
    helper.chmod(0o755)
    return helper


def _config(tmp_path: Path, body: str) -> Path:
    cfg = tmp_path / "calendars.toml"
    cfg.write_text(f"[calendars]\n{body}\n")
    return cfg


SHARED = 'shared = { name = "Family", write = true, mirror = ["life"] }'


def test_nothing_is_written_unless_a_calendar_opts_in_to_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _config(tmp_path, 'plain = "Chores"')  # read-only: no write, no mirror
    missing = tmp_path / "no-helper"  # never reached
    code = main(["--calendars", str(cfg), "--helper", str(missing)], _fleet(tmp_path))
    assert code == 0
    assert "no calendar opted in for writing" in capsys.readouterr().out


def test_an_opted_in_calendar_gets_its_repos_events_and_apply_is_explicit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _config(tmp_path, SHARED)
    base = ["--calendars", str(cfg), "--helper", str(_stand_in(tmp_path))]
    assert main(base, _fleet(tmp_path)) == 0
    plan = capsys.readouterr().out
    assert "== shared: 2 dated waypoints of life" in plan
    assert "ARGS --write-calendar Family EVENTS 2" in plan
    assert "--apply" not in plan
    assert main([*base, "--apply"], _fleet(tmp_path)) == 0
    applied = capsys.readouterr().out
    assert "ARGS --write-calendar Family --apply EVENTS 2" in applied


def test_a_refusal_from_the_helper_is_the_commands_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _config(tmp_path, SHARED)
    refusing = _stand_in(tmp_path, code=2)
    argv = ["--calendars", str(cfg), "--helper", str(refusing), "--apply"]
    assert main(argv, _fleet(tmp_path)) == 2
    gone = main(
        ["--calendars", str(cfg), "--helper", str(tmp_path / "gone")], _fleet(tmp_path)
    )
    assert gone == 2
    assert "is missing" in capsys.readouterr().out
