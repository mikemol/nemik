"""nemik:W149: nemik-wake --alarms lists alarms that fired in a window on open waypoints."""

import json
from datetime import datetime, timezone

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.wake import fired_alarms

UTC = timezone.utc


def _graph(tmp_path):
    q = tmp_path / "q.json"
    q.write_text(json.dumps({"version": 1, "project_root": "/x", "counter": 3, "residue": [], "waypoints": [
        {"symbol": "W9", "title": "cpr", "status": "ready", "due": "20261001T220000Z", "alarms": ["RELATED=END:-PT2H"]},
        {"symbol": "W30", "title": "drill", "status": "ready", "dtstart": "TZID=America/Detroit:20261005T180000",
         "rrule": "FREQ=WEEKLY;BYDAY=MO", "occurrences": {"TZID=America/Detroit:20261012T180000": "x"},
         "alarms": ["-PT15M"]},
        {"symbol": "W1", "title": "closed", "status": "done", "due": "20261001T220000Z", "alarms": ["RELATED=END:-PT2H"]},
    ]}))
    return queue_graph("life", q)


def test_fired_alarms_in_a_window_with_owner_liveness(tmp_path) -> None:
    g = _graph(tmp_path)
    live = {"life": {"verdict": "ok"}}
    got = fired_alarms(g, datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 20, tzinfo=UTC), live)
    assert [(a["ref"], a["at"], a["recurrence_id"][-15:], a["state"]) for a in got] == [
        ("life:W9", "2026-10-01T20:00:00Z", "", "awake"),
        ("life:W30", "2026-10-05T21:45:00Z", "20261005T180000", "awake"),
        # 10-12 completed; 10-19 fires
        ("life:W30", "2026-10-19T21:45:00Z", "20261019T180000", "awake"),
    ]  # the done waypoint W1 never fires


def test_a_bad_alarm_is_reported_not_fatal(tmp_path) -> None:
    g = _graph(tmp_path)
    from nemik.adapter import NEMIK, waypoint_uri
    from rdflib import Literal

    g.add((waypoint_uri("life", "W9"), NEMIK.alarm, Literal("not-a-trigger")))
    got = fired_alarms(g, datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 2, tzinfo=UTC), {})
    assert any(a.get("error") for a in got) and any(a["at"] == "2026-10-01T20:00:00Z" for a in got)


def test_alarms_nudge_delivers_each_firing_once(tmp_path, capsys) -> None:
    """nemik:W167: --alarms --nudge prints a firing on the first run only, sharing the nudges state."""
    from nemik.wake import main

    g, state = _graph(tmp_path), tmp_path / "nudges.json"
    state.write_text(json.dumps({"life": 1.0}))  # a repo nudge already recorded there
    argv = ["--alarms", "--nudge", "--json", "--since", "2026-10-01T00:00:00+00:00",
            "--until", "2026-10-20T00:00:00+00:00", "--nudges-state", str(state), "--liveness", str(tmp_path / "none")]
    main(argv, g)
    first = json.loads(capsys.readouterr().out)["alarms"]
    main(argv, g)
    second = json.loads(capsys.readouterr().out)["alarms"]
    assert first and second == []
    assert json.loads(state.read_text())["life"] == 1.0  # the repo nudge state survives
