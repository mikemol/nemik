# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Read a parsed TOML value through builtin types, so tomllib's Any stops at one call (nemik:W1187).

`tomllib.loads` answers dict[str, Any], and every index, get and loop over it is an Any expression
for mypy. A reader passes that one result through `table`, then reads each part with `tables` (an
array of tables) or `strings` (an array of strings); each answers a builtin type and an empty one
for any other shape, so a malformed file reads as missing, not as a crash in the reader. Pure, with
no import and no `X | None` annotation (the pinned Codon cannot compile one), like nemik.tiers and
nemik.adoption, so the Codon census can compile it.
"""


def table(value: object) -> dict[str, object]:
    """Read a TOML value as a table, or an empty one when it is anything else.

    Returns:
        The table's entries, keyed by string.

    """
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def tables(value: object) -> list[dict[str, object]]:
    """Read a TOML value as an array of tables, or an empty list when it is anything else.

    Returns:
        One table per element.

    """
    return [table(v) for v in value] if isinstance(value, list) else []


def strings(value: object) -> list[str]:
    """Read a TOML value as an array of strings, or an empty list when it is anything else.

    Returns:
        One string per element.

    """
    return [str(v) for v in value] if isinstance(value, list) else []
