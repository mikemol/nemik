"""nemik:W129: a waypoint's alarm resolves to the instant it fires; VTODOs carry it as a VALARM."""

from datetime import UTC, datetime

from nemik.alarm import duration, fires_at
from nemik.vtodo import vtodos


def test_duration_reads_every_rfc5545_part() -> None:
    assert duration("-PT15M").total_seconds() == -900
    assert duration("P1DT2H").total_seconds() == 93600
    assert duration("+P1W").days == 7


def test_relative_triggers_count_from_their_anchor() -> None:
    start, due = "TZID=America/Detroit:20261001T163000", "20261001T220000Z"
    # 4:30 PM EDT is 20:30 UTC; 15 minutes before is 20:15.
    assert fires_at("-PT15M", dtstart=start) == datetime(
        2026, 10, 1, 20, 15, tzinfo=UTC
    )
    assert fires_at("RELATED=START:-PT15M", dtstart=start) == datetime(
        2026, 10, 1, 20, 15, tzinfo=UTC
    )
    assert fires_at("RELATED=END:-PT2H", due=due) == datetime(
        2026, 10, 1, 20, 0, tzinfo=UTC
    )
    assert fires_at("VALUE=DATE-TIME:20261001T190000Z") == datetime(
        2026, 10, 1, 19, 0, tzinfo=UTC
    )
    assert (
        fires_at("RELATED=END:-PT2H") is None
    )  # anchor unset (only a hand edit can do this)


def test_vtodo_carries_each_alarm_as_a_display_valarm() -> None:
    ask = {
        "ref": "life:W9",
        "title": "cpr",
        "category": "needs-you",
        "ask": "operator: act attend",
        "waiting": [],
        "same_ask": [],
        "due": "20261001T220000Z",
        "alarms": ["RELATED=END:-PT2H", "VALUE=DATE-TIME:20261001T190000Z"],
    }
    (todo,) = vtodos([ask], {"life"})
    assert "TRIGGER;RELATED=END:-PT2H" in todo
    assert "TRIGGER;VALUE=DATE-TIME:20261001T190000Z" in todo
    assert todo.count("BEGIN:VALARM") == 2 and "ACTION:DISPLAY" in todo


def test_vtodo_carries_recurrence_as_stored() -> None:
    """mtools:W309: RRULE verbatim, each EXDATE in its stored value form."""
    ask = {
        "ref": "life:W30",
        "title": "drill",
        "category": "needs-you",
        "ask": "operator: act drill",
        "waiting": [],
        "same_ask": [],
        "dtstart": "TZID=America/Detroit:20261005T180000",
        "rrule": "FREQ=WEEKLY;BYDAY=MO",
        "exdates": ["TZID=America/Detroit:20261012T180000"],
    }
    (todo,) = vtodos([ask], {"life"})
    assert "RRULE:FREQ=WEEKLY;BYDAY=MO" in todo
    assert "EXDATE;TZID=America/Detroit:20261012T180000" in todo


def test_recurring_alarms_fire_per_occurrence_skipping_exdates_and_completed() -> None:
    """nemik:W145: weekly Mondays 6 PM Detroit, 15 min before; 10-12 excluded, 10-19 completed."""
    from nemik.alarm import fires_between

    got = fires_between(
        "-PT15M",
        datetime(2026, 10, 1, tzinfo=UTC),
        datetime(2026, 11, 10, tzinfo=UTC),
        dtstart="TZID=America/Detroit:20261005T180000",
        rrule="FREQ=WEEKLY;BYDAY=MO",
        exdates=("TZID=America/Detroit:20261012T180000",),
        done={"TZID=America/Detroit:20261019T180000": "20261019T230000Z"},
    )
    assert [(at.strftime("%m-%d %H:%M"), rid[-15:]) for at, rid in got] == [
        ("10-05 21:45", "20261005T180000"),  # EDT: 17:45 local = 21:45 UTC
        ("10-26 21:45", "20261026T180000"),
        (
            "11-02 22:45",
            "20261102T180000",
        ),  # after DST ends: EST, 17:45 local = 22:45 UTC
        ("11-09 22:45", "20261109T180000"),
    ]


def test_one_shot_and_absolute_alarms_fire_once_inside_the_window() -> None:
    from nemik.alarm import fires_between

    w = (datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 2, tzinfo=UTC))
    assert fires_between("RELATED=END:-PT2H", *w, due="20261001T220000Z") == [
        (datetime(2026, 10, 1, 20, 0, tzinfo=UTC), "")
    ]
    assert fires_between(
        "VALUE=DATE-TIME:20261001T190000Z", *w, dtstart="20261001", rrule="FREQ=DAILY"
    ) == [(datetime(2026, 10, 1, 19, 0, tzinfo=UTC), "")]
    # fires 10-01 21:45Z, outside a 10-03 window
    assert (
        fires_between(
            "-PT15M",
            datetime(2026, 10, 3, tzinfo=UTC),
            datetime(2026, 10, 4, tzinfo=UTC),
            dtstart="20261001T220000Z",
        )
        == []
    )
    assert fires_between("-PT15M", *w, dtstart="20261001T220000Z") == [
        (datetime(2026, 10, 1, 21, 45, tzinfo=UTC), "")
    ]


def test_adapter_carries_recurrence_and_completed_occurrences(tmp_path) -> None:
    import json

    from nemik.adapter import NEMIK, queue_graph, waypoint_uri

    q = tmp_path / "q.json"
    q.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": "/x",
                "counter": 1,
                "residue": [],
                "waypoints": [
                    {
                        "symbol": "W30",
                        "title": "t",
                        "status": "ready",
                        "dtstart": "20261005",
                        "rrule": "FREQ=WEEKLY",
                        "exdates": ["20261012"],
                        "occurrences": {"20261019": "20261019T230000Z"},
                        "alarms": ["-PT1H"],
                    }
                ],
            }
        )
    )
    g = queue_graph("life", q)
    n = waypoint_uri("life", "W30")
    assert str(g.value(n, NEMIK.rrule)) == "FREQ=WEEKLY"
    assert {str(x) for x in g.objects(n, NEMIK.exdate)} == {"20261012"}
    assert {str(x) for x in g.objects(n, NEMIK.occurrenceDone)} == {"20261019"}
    assert {str(x) for x in g.objects(n, NEMIK.alarm)} == {"-PT1H"}
