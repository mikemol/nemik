# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W234/W236: marks are read from the writer's file, and a stale one is never current."""

import json
from datetime import UTC, datetime

from nemik.marks import (
    DERIVED,
    EMPTY,
    MARK,
    STALE,
    UNREADABLE,
    Mark,
    epoch_seconds,
    mark_source,
    marks_from_text,
    parse_mark,
)
from nemik.tomlview import table

NOW = "2026-10-08T12:00:00Z"
VERSION = "v1"
BAD_LINES = 2


def _mark(as_of: str, version: str = VERSION) -> dict[str, object]:
    return {"as_of": as_of, "policy_version": version, "symbol": "W1", "verdict": {}}


def _source(as_of: str, version: str = VERSION, now: str = NOW) -> str:
    """Judge a W1 mark stamped `as_of` under `version`.

    Returns:
        The provenance word.

    """
    marks = {"W1": Mark("W1", version, as_of)}
    return mark_source(marks, "W1", now, VERSION)


def test_no_mark_is_derived() -> None:
    """No mark is derived."""
    assert mark_source({}, "W1", NOW, VERSION) == DERIVED


def test_a_fresh_mark_judged_by_this_policy_is_a_mark() -> None:
    """A fresh mark judged by this policy is a mark."""
    assert _source("2026-10-08T11:30:00Z") == MARK
    assert _source("2026-10-08T11:30:00+00:00", now="2026-10-08T12:00:00+00:00") == MARK


def test_a_mark_older_than_the_policy_max_age_is_stale() -> None:
    """A mark older than the policy max age is stale."""
    assert _source("2026-10-08T10:00:00Z") == STALE


def test_a_mark_judged_by_another_policy_is_stale_however_fresh() -> None:
    """A mark judged by another policy is stale however fresh."""
    assert _source(NOW, "v0") == STALE


def test_an_unreadable_as_of_is_stale_never_current() -> None:
    """An unreadable as of is stale never current."""
    assert _source("yesterday") == STALE
    assert _source("2026-10-08T11:59:00") == STALE


def test_the_latest_mark_per_symbol_wins_and_bad_lines_are_counted() -> None:
    """The latest mark per symbol wins and bad lines are counted."""
    older, newer = _mark("2026-10-08T10:00:00Z"), _mark("2026-10-08T11:00:00Z")
    lines = [json.dumps(older), "not json", json.dumps(newer), '{"no": 1}', ""]
    marks, unreadable = marks_from_text("\n".join(lines))
    assert marks["W1"].as_of == "2026-10-08T11:00:00Z"
    assert unreadable == BAD_LINES


def test_no_text_reads_empty() -> None:
    """An absent marks file reaches the reader as no text, and reads empty."""
    assert marks_from_text("") == ({}, 0)


def _reference(raw: str) -> tuple[str, str, str]:
    """Read a marks line the way nemik did before nemik:W1719: json.loads, then str fields.

    Returns:
        (symbol, policy_version, as_of), each empty when absent or not text; all empty when the
        line is no mark.

    """
    try:
        loaded: object = json.loads(raw)
    except json.JSONDecodeError:
        return "", "", ""
    if not isinstance(loaded, dict):
        return "", "", ""
    fields = table(loaded)
    symbol, version, as_of = (
        fields.get("symbol"),
        fields.get("policy_version"),
        fields.get("as_of"),
    )
    if not isinstance(symbol, str):
        return "", "", ""
    return (
        symbol,
        version if isinstance(version, str) else "",
        as_of if isinstance(as_of, str) else "",
    )


def _line(**fields: object) -> str:
    return json.dumps(fields)


LINES = [
    json.dumps(_mark("2026-10-08T11:30:00Z")),
    _line(symbol="W2", policy_version="v1", as_of="x", op="add"),
    _line(symbol="W3"),
    _line(symbol=3, policy_version="v1", as_of="x"),
    _line(symbol="W4", policy_version=7, as_of=["a"]),
    _line(symbol="W5", policy_version=None, as_of={"a": 1}),
    _line(symbol="W6", verdict={"nested": [1, 2, {"symbol": "W9"}]}),
    '{"symbol": "W7", "symbol": "W8", "as_of": "1", "as_of": "2"}',
    '{"symbol": "W1"} trailing',
    '{"symbol": "W1"',
    '["symbol"]',
    '"W1"',
    "null",
    "{}",
    "",
    "not json",
]


def test_the_reader_agrees_with_the_json_loads_reader_it_replaced() -> None:
    """Over odd lines: duplicate keys, non-text fields, nesting, trailing text, bad JSON."""
    for raw in LINES:
        got = parse_mark(raw)
        assert (got.symbol, got.policy_version, got.as_of) == _reference(raw), raw


def test_a_line_that_is_no_mark_is_empty() -> None:
    """MUTANT: reading a bad line as a mark would count it as read."""
    assert parse_mark("not json") is EMPTY
    assert not parse_mark('{"as_of": "x"}').symbol


INSTANTS = [
    "1970-01-01T00:00:00",
    "1999-12-31T23:59:59",
    "2000-02-29T00:00:00",
    "2023-02-28T23:59:59",
    "2024-02-29T12:30:45",
    "2026-10-08T12:00:00",
    "2026-12-31T23:59:59",
    "2100-03-01T00:00:00",
    "2400-02-29T06:07:08",
]
FULLWIDTH_YEAR = (
    "".join(chr(0xFF10 + digit) for digit in (2, 0, 2, 6)) + "-10-08T12:00:00Z"
)


def _python_epoch(naive: str) -> int:
    return int(datetime.fromisoformat(naive).replace(tzinfo=UTC).timestamp())


def test_the_hand_read_instant_agrees_with_datetime_for_every_utc_spelling() -> None:
    """Both suffixes the writer may use read as datetime reads them."""
    for naive in INSTANTS:
        want = _python_epoch(naive)
        assert epoch_seconds(naive + "Z") == want, naive
        assert epoch_seconds(naive + "+00:00") == want, naive


def test_an_instant_nemik_does_not_read_is_unreadable_never_a_guess() -> None:
    """Another offset, no offset, a fraction, an impossible date, a time before 1970."""
    for text in [
        "",
        "yesterday",
        "2026-10-08T12:00:00",
        "2026-10-08T12:00:00+01:00",
        "2026-10-08T12:00:00.5Z",
        "2026-10-08 12:00:00Z",
        "2026-10-08T12:00Z",
        "2026-13-08T12:00:00Z",
        "2026-00-08T12:00:00Z",
        "2026-10-00T12:00:00Z",
        "2026-02-29T12:00:00Z",
        "2026-04-31T12:00:00Z",
        "2026-10-08T24:00:00Z",
        "2026-10-08T12:60:00Z",
        "2026-10-08T12:00:60Z",
        "1969-12-31T23:59:59Z",
        "2026-1x-08T12:00:00Z",
        FULLWIDTH_YEAR,
    ]:
        assert epoch_seconds(text) == UNREADABLE, text
