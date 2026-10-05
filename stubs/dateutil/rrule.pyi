"""Stub for the one corner of python-dateutil nemik uses (nemik.alarm.fires_between).

Only `rrulestr(...).between(...)` is declared. Add a name here when a caller needs it; do not
widen this to the whole library (that is what the types-python-dateutil wheel is for).
"""

from datetime import datetime

class rrulebase:
    def between(
        self,
        after: datetime,
        before: datetime,
        inc: bool = ...,
        count: int = ...,
    ) -> list[datetime]: ...

def rrulestr(s: str, *, dtstart: datetime | None = ...) -> rrulebase: ...
