"""nemik:W197 (life's ask): dated waypoints as VEVENTs with a stable UID, ready to write."""

import json
from pathlib import Path

import pytest
from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.calwrite import event_times, events, feed, uid


def _queue(tmp_path: Path, repo: str, waypoints: list[dict]) -> Graph:
    path = tmp_path / f"{repo}.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": "/x",
                "counter": len(waypoints),
                "residue": [],
                "waypoints": waypoints,
            }
        )
    )
    return queue_graph(repo, path)


def _fleet(tmp_path: Path) -> Graph:
    life = _queue(
        tmp_path,
        "life",
        [
            {
                "symbol": "W9",
                "title": "cpr class",
                "status": "ready",
                "due": "20261001T220000Z",
                "alarms": ["RELATED=END:-PT2H"],
            },
            {
                "symbol": "W30",
                "title": "drill",
                "status": "ready",
                "dtstart": "TZID=America/Detroit:20261005T180000",
                "rrule": "FREQ=WEEKLY;BYDAY=MO",
                "occurrences": {"TZID=America/Detroit:20261012T180000": "done"},
                "alarms": ["-PT15M"],
            },
            {"symbol": "W1", "title": "closed", "status": "done", "due": "20261001"},
            {"symbol": "W5", "title": "no date at all", "status": "ready"},
        ],
    )
    life += _queue(
        tmp_path,
        "mtools",
        [
            {
                "symbol": "W2",
                "title": "trip",
                "status": "ready",
                "dtstart": "20261010",
                "due": "20261012",
            }
        ],
    )
    return life


def test_only_open_dated_waypoints_of_the_opted_in_repos_become_events(
    tmp_path: Path,
) -> None:
    g = _fleet(tmp_path)
    got = [e[1] for e in events(g, ["life"])]
    want = [f"UID:{uid('life:W9')}", f"UID:{uid('life:W30')}"]
    assert got == want  # done and undated are absent
    assert events(g, ["life", "mtools"])[-1][1] == f"UID:{uid('mtools:W2')}"
    assert events(g, []) == []  # nothing is mirrored implicitly


def test_a_due_only_waypoint_sits_at_its_deadline_with_an_end_for_its_alarm(
    tmp_path: Path,
) -> None:
    (cpr, _) = events(_fleet(tmp_path), ["life"])
    assert "DTSTART:20261001T220000Z" in cpr and "DTEND:20261001T220000Z" in cpr
    assert "SUMMARY:cpr class" in cpr and "DESCRIPTION:nemik-ref: life:W9" in cpr
    assert "TRIGGER;RELATED=END:-PT2H" in cpr and "ACTION:DISPLAY" in cpr


def test_a_recurring_waypoint_keeps_its_rule_and_drops_a_completed_occurrence(
    tmp_path: Path,
) -> None:
    (_, drill) = events(_fleet(tmp_path), ["life"])
    assert "DTSTART;TZID=America/Detroit:20261005T180000" in drill
    assert "RRULE:FREQ=WEEKLY;BYDAY=MO" in drill
    assert "EXDATE;TZID=America/Detroit:20261012T180000" in drill
    assert "TRIGGER:-PT15M" in drill


def test_an_all_day_range_ends_the_day_after_its_inclusive_due(
    tmp_path: Path,
) -> None:
    (trip,) = events(_fleet(tmp_path), ["mtools"])
    assert "DTSTART;VALUE=DATE:20261010" in trip
    assert "DTEND;VALUE=DATE:20261013" in trip


@pytest.mark.parametrize(
    ("dtstart", "due", "needs_end", "want"),
    [
        ("", "20261001T220000Z", True, ("20261001T220000Z", "20261001T220000Z")),
        ("", "20261001T220000Z", False, ("20261001T220000Z", "")),
        ("20261010", "20261010", False, ("20261010", "")),
        ("20261010", "20261011", False, ("20261010", "20261012")),
        (
            "20261001T100000Z",
            "20261001T110000Z",
            False,
            ("20261001T100000Z", "20261001T110000Z"),
        ),
        ("20261001T120000Z", "20261001T110000Z", False, ("20261001T120000Z", "")),
        ("20261010", "20261010T120000Z", False, ("20261010", "")),
        (
            "TZID=America/Detroit:20261001T100000",
            "20261001T110000Z",
            False,
            ("TZID=America/Detroit:20261001T100000", ""),
        ),
    ],
)
def test_event_times_never_invent_a_wrong_end(
    dtstart: str, due: str, needs_end: bool, want: tuple[str, str]
) -> None:
    assert event_times(dtstart, due, needs_end) == want


def test_the_feed_is_crlf_folded_deterministic_and_carries_only_what_was_asked(
    tmp_path: Path,
) -> None:
    g = _fleet(tmp_path)
    text = feed(g, ["life"])
    assert text == feed(g, ["life"])  # a function of the queues alone
    assert text.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n")
    assert text.endswith("END:VEVENT\r\nEND:VCALENDAR\r\n")
    assert "life:W2" not in text and "trip" not in text  # mtools was not opted in
    long = _queue(
        tmp_path,
        "life",
        [{"symbol": "W7", "title": "x" * 200, "status": "ready", "due": "20261001"}],
    )
    wrapped = feed(long, ["life"])
    assert all(len(line.encode()) <= 75 for line in wrapped.split("\r\n"))
