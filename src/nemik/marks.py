# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W234/W236: read the verdict marks mtools' writer persists, never re-derive them privately.

The marks file is `.claude/paths-forward.marks.jsonl` beside the queue (mtools:W851, agreed in
mtools:W849/W852): append-only, one JSON object per transition, apart from the text ledger. A
record is {as_of, op, symbol, policy_version, input_digest, verdict}; `policy_version` is the
sha256 of the policy file that judged it and `as_of` is the same `now` the policy received.

A symbol with no mark is `derived`: judged now, because it was minted before the hook. A mark that
is older than the policy's `max_age_seconds`, or was judged by another policy, is `stale`: it is
printed as such and never read as current. An unreadable line is counted, not skipped silently.

This module reads text and touches no path: the caller reads the file (nemik:W1719).
"""

from nemik.jsonparse import Parser

MARKS = "paths-forward.marks.jsonl"
# The policy's own default (data.realizability_config.max_age_seconds, mtools:W850); a mark older
# than this is stale for the same reason a lapsed fact floors its gate.
MAX_AGE_SECONDS = 3600
MARK, DERIVED, STALE = "mark", "derived", "stale"
OBJECT = "object"
STRING = "str"
UNREADABLE = -1
EPOCH_YEAR = 1970
DAYS_PER_400_YEARS = 146097
DAYS_0000_TO_EPOCH = 719468
MONTHS = 12
MARCH = 3
FEBRUARY = 2
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
INSTANT_LENGTH = 19
# (start, end) of year, month, day, hour, minute, second in `YYYY-MM-DDTHH:MM:SS`
FIELD_SPANS = [(0, 4), (5, 7), (8, 10), (11, 13), (14, 16), (17, 19)]
SEPARATORS = [(4, "-"), (7, "-"), (10, "T"), (13, ":"), (16, ":")]
HOURS = 24
MINUTES = 60
SECONDS = 60
SECONDS_PER_DAY = 86400


class Mark:
    """The three fields of a mark that nemik reads, as text (nemik:W1719)."""

    symbol: str
    policy_version: str
    as_of: str

    def __init__(self, symbol: str, policy_version: str, as_of: str) -> None:
        """Hold the symbol, the policy that judged and the instant it judged at."""
        self.symbol = symbol
        self.policy_version = policy_version
        self.as_of = as_of


# no mark: a line that is not one, or a symbol the writer has made none for
EMPTY = Mark("", "", "")


def parse_mark(raw: str) -> Mark:
    """Read one marks line as a Mark, with the Codon-compatible JSON parser (nemik:W1719).

    A field that is not a string reads as empty, so a non-string policy_version is never equal to
    a version and a non-string as_of is not an instant: the mark reads as stale, as before.

    Returns:
        The mark, or EMPTY when the line is not JSON, not an object or names no symbol.

    """
    parser = Parser(raw)
    at = parser.value()
    parser.skip()
    if not parser.ok or at < 0 or parser.pos != len(raw):
        return EMPTY
    node = parser.tree.nodes[at]
    if node.kind != OBJECT:
        return EMPTY
    symbol = ""
    policy_version = ""
    as_of = ""
    for at_key in range(len(node.keys)):
        key = node.keys[at_key]
        leaf = parser.tree.nodes[node.kids[at_key]]
        text = leaf.text if leaf.kind == STRING else ""
        if key == "symbol":
            symbol = text
        elif key == "policy_version":
            policy_version = text
        elif key == "as_of":
            as_of = text
    return Mark(symbol, policy_version, as_of) if symbol else EMPTY


def marks_from_text(text: str) -> tuple[dict[str, Mark], int]:
    """Read the latest mark per symbol from the text of the marks file.

    Returns:
        (the latest mark for each symbol, the count of lines that were not a mark).

    """
    latest: dict[str, Mark] = {}
    unreadable = 0
    for raw in text.splitlines():
        if not raw.strip():
            continue
        mark = parse_mark(raw)
        if not mark.symbol:
            unreadable += 1
            continue
        latest[mark.symbol] = mark
    return latest, unreadable


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _fields(body: str) -> list[int]:
    """Cut `YYYY-MM-DDTHH:MM:SS` into its six numbers.

    Returns:
        year, month, day, hour, minute, second; empty when the text is not that shape.

    """
    if len(body) != INSTANT_LENGTH:
        return []
    for at, sep in SEPARATORS:
        if body[at] != sep:
            return []
    numbers: list[int] = []
    for start, end in FIELD_SPANS:
        value = 0
        for char in body[start:end]:
            if char < "0" or char > "9":
                return []
            value = value * 10 + (ord(char) - ord("0"))
        numbers.append(value)
    return numbers


def epoch_seconds(text: str) -> int:
    """Read a UTC instant `YYYY-MM-DDTHH:MM:SS` ending in `Z` or `+00:00` as epoch seconds.

    Codon's datetime.fromisoformat rejects any offset, so the writer's instants are read here, by
    hand and the same under CPython and Codon (nemik:W1719). Anything else, another offset, a
    fraction, a naive time, an impossible date or one before 1970, is unreadable.

    Returns:
        Seconds since 1970-01-01T00:00:00Z, or -1 when the text is not such an instant.

    """
    body = text
    if body.endswith("Z"):
        body = body[:-1]
    elif body.endswith("+00:00"):
        body = body[:-6]
    else:
        return UNREADABLE
    numbers = _fields(body)
    if not numbers:
        return UNREADABLE
    year, month, day, hour, minute, second = numbers
    if year < EPOCH_YEAR or month < 1 or month > MONTHS or day < 1:
        return UNREADABLE
    longest = DAYS_IN_MONTH[month - 1] + (
        1 if month == FEBRUARY and _is_leap(year) else 0
    )
    if day > longest or hour >= HOURS or minute >= MINUTES or second >= SECONDS:
        return UNREADABLE
    # days from civil (Howard Hinnant), the year starting in March
    shifted = year - (1 if month < MARCH else 0)
    era = shifted // 400
    year_of_era = shifted - era * 400
    day_of_year = (153 * (month + (-3 if month >= MARCH else 9)) + 2) // 5 + day - 1
    day_of_era = year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year
    days = era * DAYS_PER_400_YEARS + day_of_era - DAYS_0000_TO_EPOCH
    return days * SECONDS_PER_DAY + hour * 3600 + minute * 60 + second


def bad_instants(marks: dict[str, Mark]) -> int:
    """Count the marks whose `as_of` is not an instant nemik reads.

    Such a mark reads as stale, and nothing else says why: a writer that began to stamp another
    offset would turn every card stale quietly. The caller prints this beside the unreadable-line
    count, so the cause is a finding (github-82, nemik:W1719).

    Returns:
        How many of the latest marks have an `as_of` that `epoch_seconds` cannot read.

    """
    count = 0
    for mark in marks.values():
        if epoch_seconds(mark.as_of) == UNREADABLE:
            count += 1
    return count


def mark_source(marks: dict[str, Mark], symbol: str, now: str, version: str) -> str:
    """Say where a symbol's verdict comes from.

    Args:
        marks: The latest mark per symbol, as `marks_from_text` gives it.
        symbol: The card's symbol.
        now: The instant the verdict is judged at, as `YYYY-MM-DDTHH:MM:SS+00:00`.
        version: The policy version that judges now.

    Returns:
        `derived` with no mark, `stale` for a lapsed or other-policy mark, else `mark`.

    """
    mark = marks.get(symbol, EMPTY)
    if not mark.symbol:
        return DERIVED
    if mark.policy_version != version:
        return STALE
    then = epoch_seconds(mark.as_of)
    current = epoch_seconds(now)
    if UNREADABLE in {then, current}:
        return STALE
    return STALE if current - then > MAX_AGE_SECONDS else MARK
