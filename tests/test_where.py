# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1128: the filter language keeps the rows its find(1)-shaped expression names."""

import pytest

from nemik.where import matches, parse

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
