"""nemik:W129: when a waypoint's alarm fires, as one UTC instant.

mtools stores each alarm as an RFC 5545 TRIGGER (mtools:W279), next to the times it counts from
(dtstart, due; mtools:W300). mtools also resolves a trigger to its instant (timevalue.fires_at,
mtools:W308), so nemik does no time arithmetic of its own (nemik:W146). This module fixes nemik's
one choice: an all-day DATE anchor counts from local midnight in the host's zone, which is the
operator's zone and matches how a calendar shows an all-day item. Firing is nemik-wake's job.
Recurrence (RRULE, mtools:W309/W310) is expanded here (fires_between, nemik:W145).
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

from mikemol.pathsforward.timevalue import duration
from mikemol.pathsforward.timevalue import fires_at as _fires_at

__all__ = ["duration", "fires_at", "fires_between", "recurrence_id"]


def fires_at(trigger: str, dtstart: str = "", due: str = "") -> datetime | None:
    """The UTC instant `trigger` fires, or None when its anchor is unset."""
    return _fires_at(trigger, dtstart, due, day_zone=datetime.now().astimezone().tzinfo)


def recurrence_id(when: datetime | date, dtstart: str) -> str:
    """An occurrence's RECURRENCE-ID written in DTSTART's own form, the key mtools:W310 uses."""
    if dtstart.startswith("TZID="):
        zone = dtstart.removeprefix("TZID=").partition(":")[0]
        assert isinstance(when, datetime)
        return f"TZID={zone}:{when.strftime('%Y%m%dT%H%M%S')}"
    if re.fullmatch(r"\d{8}", dtstart):
        return when.strftime("%Y%m%d")
    assert isinstance(when, datetime)
    return when.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fires_between(trigger: str, start: datetime, end: datetime, *, dtstart: str = "", due: str = "",
                  rrule: str = "", exdates: tuple[str, ...] = (), done: dict | None = None,
                  ) -> list[tuple[datetime, str]]:
    """Every (UTC instant, RECURRENCE-ID) in [start, end) at which `trigger` fires (nemik:W145).

    Without a rule: the one instant, RECURRENCE-ID "". With one (mtools:W309): each occurrence of
    the rule from DTSTART shifts the trigger by its distance from DTSTART (a DUE-relative trigger
    too, since an occurrence's DUE moves with its start), except occurrences that are EXDATEs or
    completed (`done`, mtools:W310's {RECURRENCE-ID: COMPLETED}). An absolute trigger fires once.
    """
    base = fires_at(trigger, dtstart, due)
    if base is None:
        return []
    if not rrule or trigger.startswith("VALUE=DATE-TIME:"):
        return [(base, "")] if start <= base < end else []
    from dateutil.rrule import rrulestr
    from mikemol.pathsforward.timevalue import parse

    first = parse(dtstart).when
    anchor = first if isinstance(first, datetime) else datetime.combine(first, time(0)).astimezone()
    offset = base - anchor  # where the trigger sits relative to each occurrence's start
    skip_at = {(w if isinstance(w := parse(x).when, datetime) else datetime.combine(w, time(0)).astimezone())
               for x in exdates}
    out = []
    # Occurrences whose firing can fall in the window: shift the window back by the offset.
    for occ in rrulestr(rrule, dtstart=anchor).between(start - offset - timedelta(seconds=1), end - offset, inc=True):
        rid = recurrence_id(occ if isinstance(first, datetime) else occ.date(), dtstart)
        if occ in skip_at or rid in (done or {}):
            continue
        at = (occ + offset).astimezone(timezone.utc)
        if start <= at < end:
            out.append((at, rid))
    return out
