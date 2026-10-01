"""nemik:W129: a waypoint's alarm resolves to the instant it fires; VTODOs carry it as a VALARM."""

from datetime import datetime, timezone

from nemik.alarm import duration, fires_at
from nemik.vtodo import vtodos

UTC = timezone.utc


def test_duration_reads_every_rfc5545_part() -> None:
    assert duration("-PT15M").total_seconds() == -900
    assert duration("P1DT2H").total_seconds() == 93600
    assert duration("+P1W").days == 7


def test_relative_triggers_count_from_their_anchor() -> None:
    start, due = "TZID=America/Detroit:20261001T163000", "20261001T220000Z"
    # 4:30 PM EDT is 20:30 UTC; 15 minutes before is 20:15.
    assert fires_at("-PT15M", dtstart=start) == datetime(2026, 10, 1, 20, 15, tzinfo=UTC)
    assert fires_at("RELATED=START:-PT15M", dtstart=start) == datetime(2026, 10, 1, 20, 15, tzinfo=UTC)
    assert fires_at("RELATED=END:-PT2H", due=due) == datetime(2026, 10, 1, 20, 0, tzinfo=UTC)
    assert fires_at("VALUE=DATE-TIME:20261001T190000Z") == datetime(2026, 10, 1, 19, 0, tzinfo=UTC)
    assert fires_at("RELATED=END:-PT2H") is None  # anchor unset (only a hand edit can do this)


def test_vtodo_carries_each_alarm_as_a_display_valarm() -> None:
    ask = {"ref": "life:W9", "title": "cpr", "category": "needs-you", "ask": "operator: act attend",
           "waiting": [], "same_ask": [], "due": "20261001T220000Z",
           "alarms": ["RELATED=END:-PT2H", "VALUE=DATE-TIME:20261001T190000Z"]}
    (todo,) = vtodos([ask], {"life"})
    assert "TRIGGER;RELATED=END:-PT2H" in todo
    assert "TRIGGER;VALUE=DATE-TIME:20261001T190000Z" in todo
    assert todo.count("BEGIN:VALARM") == 2 and "ACTION:DISPLAY" in todo
