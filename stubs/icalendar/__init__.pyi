"""nemik:W602: the part of icalendar the round-trip tests use, typed (the library ships none)."""

class Component:
    name: str
    def walk(self, name: str | None = None) -> list[Component]: ...
    def get(self, key: str) -> object: ...

class Calendar(Component):
    @classmethod
    def from_ical(cls, st: str | bytes) -> Calendar: ...
