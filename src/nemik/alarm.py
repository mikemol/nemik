"""nemik:W129: when a waypoint's alarm fires, as one UTC instant.

mtools stores each alarm as an RFC 5545 TRIGGER and validates it (mtools:W279), with the times it
counts from (dtstart, due; mtools:W300). The grammar is mtools': its parsers read every value here.
What mtools does not do is the arithmetic, the instant a relative trigger names, because firing is
nemik's job (nemik-wake). Recurrence (RRULE, mtools:W278) is not handled yet: each trigger fires once.

A DATE anchor (an all-day dtstart or due) counts from that day's local midnight, in the host's
zone. That's the operator's zone, which is how a calendar shows an all-day item.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

from mikemol.pathsforward.timevalue import parse, parse_trigger

_PART = re.compile(r"(\d+)([WDHMS])")
_UNIT = {"W": timedelta(weeks=1), "D": timedelta(days=1), "H": timedelta(hours=1),
         "M": timedelta(minutes=1), "S": timedelta(seconds=1)}


def duration(text: str) -> timedelta:
    """An RFC 5545 dur-value mtools has already validated: [+-]P[nW|nD][T nH nM nS]."""
    sign = -1 if text.startswith("-") else 1
    return sign * sum((int(n) * _UNIT[u] for n, u in _PART.findall(text.lstrip("+-").removeprefix("P"))),
                      timedelta())


def _instant(value: str) -> datetime:
    when = parse(value).when
    if isinstance(when, datetime):
        return when
    assert isinstance(when, date)
    return datetime.combine(when, time(0)).astimezone()  # local midnight of an all-day value


def fires_at(trigger: str, dtstart: str = "", due: str = "") -> datetime | None:
    """The UTC instant `trigger` fires, or None when its anchor is unset."""
    t = parse_trigger(trigger)
    if t.related is None:
        return parse(trigger.removeprefix("VALUE=DATE-TIME:")).when.astimezone(timezone.utc)
    anchor = dtstart if t.related == "START" else due
    if not anchor:
        return None  # mtools refuses this at write; a queue edited by hand can still carry it
    offset = trigger.split(":", 1)[1] if trigger.startswith("RELATED=") else trigger
    return (_instant(anchor) + duration(offset)).astimezone(timezone.utc)
