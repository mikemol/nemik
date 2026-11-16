# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1128: the filter language keeps the rows its find(1)-shaped expression names."""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from nemik.history import kept_events
from nemik.where import EVENT_FIELDS, FIELDS, event_row, matches, parse, parse_fields

if TYPE_CHECKING:
    from nemik.cardevents import Event

READY = {
    "cite": "nemik:W5",
    "age_days": "3.0",
    "status": "ready",
    "flag": "untouched",
    "blocked_on": "",
    "title": "Pay the D103 family",
}
BLOCKED = {
    "cite": "gabion:W9",
    "age_days": "30.5",
    "status": "blocked",
    "flag": "stuck",
    "blocked_on": "gabion:W11, operator",
    "title": "Dormant watch",
}
YOUNG = {**READY, "cite": "nemik:W6", "age_days": "0.5"}
OLDEST = "status=ready and not blocked_on=* and age>2d"


def _kept(expression: str) -> list[str]:
    """List the cites the expression keeps from the sample rows.

    Returns:
        The cites, in the sample's order.

    """
    postfix = parse(expression)
    return [row["cite"] for row in (READY, BLOCKED, YOUNG) if matches(postfix, row)]


def test_not_blocked_is_the_first_expression() -> None:
    """The ask: the oldest cards that are not blocked, with an age floor."""
    assert _kept(OLDEST) == ["nemik:W5"]
    assert _kept("not blocked_on=*") == ["nemik:W5", "nemik:W6"]
    assert _kept("blocked_on=*") == ["gabion:W9"]


def test_text_fields_compare_by_equality_and_containment() -> None:
    """Status and repo are exact, title takes ~ for contains, any case."""
    assert _kept("status=blocked") == ["gabion:W9"]
    assert _kept("repo=gabion") == ["gabion:W9"]
    assert _kept("repo!=nemik") == ["gabion:W9"]
    assert _kept("title~d103") == ["nemik:W5", "nemik:W6"]
    assert _kept('title~"dormant watch"') == ["gabion:W9"]
    assert _kept("flag=stuck") == ["gabion:W9"]


def test_an_age_compares_in_minutes_hours_and_days() -> None:
    """An age takes a number and a unit; 3.0 days is 72h and more than 2d."""
    assert _kept("age>2d") == ["nemik:W5", "gabion:W9"]
    assert _kept("age<13h") == ["nemik:W6"]
    assert _kept("age<=12h") == ["nemik:W6"]
    assert _kept("age>=72h and age<=3d") == ["nemik:W5"]
    assert _kept("age>800m") == ["nemik:W5", "gabion:W9"]


def test_or_and_parentheses_group_as_in_find() -> None:
    """Binding is tighter for and than for or; parentheses override."""
    assert _kept("status=blocked or status=ready and age<1d") == [
        "gabion:W9",
        "nemik:W6",
    ]
    assert _kept("(status=blocked or status=ready) and age<1d") == ["nemik:W6"]
    assert _kept("not (status=ready or repo=gabion)") == []


def test_an_empty_filter_keeps_every_row() -> None:
    """No expression means no filter."""
    assert parse("") == []
    assert _kept("   ") == ["nemik:W5", "gabion:W9", "nemik:W6"]


def test_a_malformed_filter_is_refused_with_what_is_wrong() -> None:
    """Unknown fields and operators, missing values, bad ages and open parentheses refuse."""
    for bad, why in (
        ("colour=red", "not a field"),
        ("status~~ready", "not an operator"),
        ("status=", "ends where a value"),
        ("(status=ready", "closing parenthesis"),
        ('title~"open', "unclosed quote"),
        ("status=ready junk", "unexpected junk"),
    ):
        with pytest.raises(ValueError, match=why):
            parse(bad)
    with pytest.raises(ValueError, match="not an age"):
        matches(parse("age>soon"), READY)
    with pytest.raises(ValueError, match="compares numbers"):
        matches(parse("status>ready"), READY)


def _event(station: str, days_ago: float, change: tuple[str, str, str, str]) -> Event:
    """Build an event whose change is `days_ago` days old.

    Returns:
        The event: station, time, field, from, to, commit.

    """
    when = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    field, old, new, sha = change
    return (station, when, field, old, new, sha)


EVENTS = [
    _event("nemik:W5", 6, ("status", "ready", "done", "abc1234")),
    _event("gabion:W9", 1, ("blocked_on", "", "gabion:W11", "def5678")),
    _event("nemik:W7", 900, ("status", "ready", "working", "0001111")),
]


def _event_cites(expression: str) -> list[str]:
    """List the stations the expression keeps from the sample events.

    Returns:
        The stations, in the sample's order.

    """
    return [event[0] for event in kept_events(EVENTS, expression)]


def test_an_event_filter_reads_the_fields_of_an_event() -> None:
    """Field, from, to, commit, repo and station name an event's parts."""
    assert _event_cites("field=status and to=done") == ["nemik:W5"]
    assert _event_cites("repo=gabion") == ["gabion:W9"]
    assert _event_cites("station=W7") == ["nemik:W7"]
    assert _event_cites("commit=def5678") == ["gabion:W9"]
    assert _event_cites("from=ready and not to=done") == ["nemik:W7"]


def test_an_event_filter_reads_the_age_of_the_change() -> None:
    """Age is how old the change is, not the card: the old change is old, the others are not."""
    assert _event_cites("age>30d") == ["nemik:W7"]
    assert _event_cites("age<30d and field=status") == ["nemik:W5"]


def test_a_card_field_is_not_an_event_field() -> None:
    """Status and title belong to a card's row; on events the filter names the field it lacks."""
    with pytest.raises(ValueError, match="status is not a field"):
        kept_events(EVENTS, "status=ready")
    assert parse_fields("status=ready", FIELDS) == parse("status=ready")


def test_an_event_field_is_not_a_card_field() -> None:
    """On cards (the default fields) `to` is refused, so the two languages stay apart."""
    with pytest.raises(ValueError, match="to is not a field"):
        parse("to=done")
    assert parse_fields("to=done", EVENT_FIELDS)


def test_event_row_gives_the_symbol_and_the_age_as_text() -> None:
    """The row carries the station's repo through cite and its symbol alone as station."""
    row = event_row(EVENTS[0], 6.5)
    assert row["cite"] == "nemik:W5"
    assert row["station"] == "W5"
    assert row["age_days"] == "6.5"
