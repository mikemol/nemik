"""nemik:W1568: the part of jsonschema the tests and tools use, typed with object (the shipped stubs answer Any)."""

from collections.abc import Iterator, Mapping, Sequence

class FormatChecker:
    def __init__(self) -> None: ...

class ValidationError(Exception):
    message: str
    absolute_path: Sequence[object]

class Draft202012Validator:
    def __init__(
        self,
        schema: Mapping[str, object],
        format_checker: FormatChecker | None = None,
    ) -> None: ...
    @classmethod
    def check_schema(cls, schema: Mapping[str, object]) -> None: ...
    def is_valid(self, instance: object) -> bool: ...
    def iter_errors(self, instance: object) -> Iterator[ValidationError]: ...

def validate(instance: object, schema: Mapping[str, object]) -> None: ...
