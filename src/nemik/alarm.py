"""nemik:W129: when a waypoint's alarm fires, as one UTC instant.

mtools stores each alarm as an RFC 5545 TRIGGER (mtools:W279), next to the times it counts from
(dtstart, due; mtools:W300). mtools also resolves a trigger to its instant (timevalue.fires_at,
mtools:W308), so nemik does no time arithmetic of its own (nemik:W146). This module fixes nemik's
one choice: an all-day DATE anchor counts from local midnight in the host's zone, which is the
operator's zone and matches how a calendar shows an all-day item. Firing is nemik-wake's job.
Recurrence (RRULE, mtools:W278) is not handled yet: each trigger fires once (nemik:W145).
"""

from __future__ import annotations

from datetime import datetime

from mikemol.pathsforward.timevalue import duration
from mikemol.pathsforward.timevalue import fires_at as _fires_at

__all__ = ["duration", "fires_at"]


def fires_at(trigger: str, dtstart: str = "", due: str = "") -> datetime | None:
    """The UTC instant `trigger` fires, or None when its anchor is unset."""
    return _fires_at(trigger, dtstart, due, day_zone=datetime.now().astimezone().tzinfo)
