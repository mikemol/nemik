# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""hostroot: luthen's host-root frontier as rows, newest per resource (nemik:W773, W774, W461).

luthen-observability publishes the root-run host's resources as one log line per node per
refresh (stream host_root_frontier, luthen-observability:W1468). The document is the latest
line per id. This module is the pure part: reading a line into a row, the choice of the latest
row per id, and whether a row is stale. Fetching the lines is endpoint.vlogs_lines; showing the
rows is nemik:W775.

The lines are read by a small reader of flat JSON objects (string keys; string, list or bare
values) in plain str code: json.loads gives Any, which the mypy house config refuses, and
Codon's JSON value cannot be narrowed, so neither json nor a cast serves a module both must
accept.
"""

from .climate import _instant

STATES = ["done", "ready", "blocked"]
# luthen refreshes hourly; past two hours without a newer line, the reading is not current
# (the stream has no freshness alert, so as_of is the only evidence).
STALE_HOURS = 2.0
SECONDS_PER_HOUR = 3600.0
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f"}
HEX_DIGITS = 4
BLANKS = " \t\r\n"


class HostRow:
    """One node of the host-root frontier as a line of the stream reported it."""

    def __init__(self, ident: str, state: str, as_of: str) -> None:
        """Hold the identity, state and stamp; the reader sets the rest as it parses."""
        self.ident = ident
        self.state = state
        self.as_of = as_of
        self.waits_for: list[str] = []
        self.gate = ""
        self.reading = ""


def _skip(text: str, at: int) -> int:
    """Skip blanks.

    Returns:
        The index of the first character at or after `at` that is not a blank.

    """
    while at < len(text) and text[at] in BLANKS:
        at += 1
    return at


def _string(text: str, at: int) -> tuple[str, int]:
    """Read the JSON string literal that starts at text[at] (its opening quote).

    Returns:
        The text it stands for and the index just past its closing quote.

    Raises:
        ValueError: When the literal is not closed.

    """
    out = ""
    at += 1
    while at < len(text):
        char = text[at]
        if char == '"':
            return out, at + 1
        if char != "\\":
            out += char
            at += 1
        elif text[at + 1 : at + 2] == "u":
            out += chr(int(text[at + 2 : at + 2 + HEX_DIGITS], 16))
            at += 2 + HEX_DIGITS
        else:
            out += ESCAPES.get(text[at + 1 : at + 2], text[at + 1 : at + 2])
            at += 2
    message = "unterminated string"
    raise ValueError(message)


def _bare(text: str, at: int) -> tuple[str, int]:
    """Read a number, true, false or null: everything up to the next , ] or }.

    Returns:
        The token and the index just past it.

    """
    end = at
    while end < len(text) and text[end] not in ",]}":
        end += 1
    return text[at:end].strip(), end


def _value(text: str, at: int) -> tuple[list[str], int]:
    """Read one value: a string or bare token as one item, a list as its items.

    Returns:
        The items and the index just past the value.

    Raises:
        ValueError: When a list is not closed.

    """
    if text[at : at + 1] == '"':
        item, at = _string(text, at)
        return [item], at
    if text[at : at + 1] != "[":
        item, at = _bare(text, at)
        return [item], at
    items: list[str] = []
    at = _skip(text, at + 1)
    while text[at : at + 1] != "]":
        if at >= len(text):
            message = "unterminated list"
            raise ValueError(message)
        part, at = _value(text, at)
        items.extend(part)
        at = _skip(text, at)
        if text[at : at + 1] == ",":
            at = _skip(text, at + 1)
    return items, at + 1


def fields(text: str) -> dict[str, list[str]]:
    """Read a flat JSON object into each key's items.

    Args:
        text: A JSON object whose values are strings, bare tokens or lists of them.

    Returns:
        {key: items}: a scalar is a one-item list, an empty list is an empty one.

    Raises:
        ValueError: When the text is not such an object.

    """
    out: dict[str, list[str]] = {}
    at = _skip(text, 0)
    if text[at : at + 1] != "{":
        message = "not a JSON object"
        raise ValueError(message)
    at = _skip(text, at + 1)
    while text[at : at + 1] != "}":
        if text[at : at + 1] != '"':
            message = "expected a key"
            raise ValueError(message)
        key, at = _string(text, at)
        at = _skip(text, at)
        if text[at : at + 1] != ":":
            message = "expected a colon"
            raise ValueError(message)
        out[key], at = _value(text, _skip(text, at + 1))
        at = _skip(text, at)
        if text[at : at + 1] == ",":
            at = _skip(text, at + 1)
    return out


def _one(body: dict[str, list[str]], key: str) -> str:
    """Read the single string a key holds.

    Returns:
        The key's first item.

    Raises:
        ValueError: When the key is absent or holds no item.

    """
    items = body.get(key, [])
    if len(items) == 0:
        message = f"no {key}"
        raise ValueError(message)
    return items[0]


def parse(message: str) -> HostRow:
    """Read one document line, the JSON luthen puts in a record's _msg.

    Args:
        message: {"id", "state", "waitsFor", "gate", "reading", "as_of"} as JSON text.

    Returns:
        The row.

    """
    body = fields(message)
    row = HostRow(_one(body, "id"), _one(body, "state"), _one(body, "as_of"))
    row.gate = _one(body, "gate")
    row.reading = _one(body, "reading")
    row.waits_for = body.get("waitsFor", [])
    return row


def _row_of(line: str) -> list[HostRow]:
    """Read one record of a VictoriaLogs answer.

    Returns:
        The row, or nothing when the line is not a record carrying a readable _msg.

    """
    try:
        return [parse(_one(fields(line), "_msg"))]
    except ValueError:
        return []


def records(lines: list[str]) -> list[HostRow]:
    """Read the lines of a VictoriaLogs answer, one record each, into rows.

    A line that is not a record is skipped, so one bad line does not hide the frontier.

    Args:
        lines: The answer's lines, in the order read.

    Returns:
        The rows, every refresh of every id; pass them to latest().

    """
    rows: list[HostRow] = []
    for line in lines:
        rows.extend(_row_of(line))
    return rows


def latest(rows: list[HostRow]) -> list[HostRow]:
    """Keep the newest row of each id; a later row wins a tie on as_of.

    Args:
        rows: Every line read from the stream, in the order read.

    Returns:
        One row per id, in the order each id first appeared.

    """
    best: dict[str, HostRow] = {}
    order: list[str] = []
    for row in rows:
        held = best.get(row.ident)
        if held is None:
            order.append(row.ident)
            best[row.ident] = row
        elif row.as_of >= held.as_of:
            best[row.ident] = row
    return [best[ident] for ident in order]


def stale(row: HostRow, now: str) -> bool:
    """Say whether a row's as_of is older than STALE_HOURS before `now`.

    Args:
        row: A row of the frontier.
        now: An ISO stamp.

    Returns:
        True when the row is older than the window, or its stamp cannot be read.

    """
    try:
        age = _instant(now) - _instant(row.as_of)
    except ValueError:
        return True
    return age.total_seconds() > STALE_HOURS * SECONDS_PER_HOUR
