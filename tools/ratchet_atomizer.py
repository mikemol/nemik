# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""ratchet_atomizer: the plan of cards for any ratchet's debt rows (nemik:W1994).

The design is in docs/ratchet-atomizer.md. A row is (ratchet, key, file, rule). The plan is one
umbrella card per ratchet and one leaf card per entry; an umbrella waits on its leaves. A title is a
function of the row alone, so a second run finds each card again. This module only plans: it reads
no file, writes no queue, and imports only the standard library.
"""

from typing import NamedTuple

UNKNOWN = "unknown"
TITLE_LIMIT = 150


class Row(NamedTuple):
    """One debt entry of one ratchet, as the census lists it."""

    ratchet: str
    key: str
    file: str
    rule: str


class Spec(NamedTuple):
    """One card to write: its title, manifest and the titles of the cards it waits on."""

    title: str
    manifest: tuple[str, ...]
    waits_on: tuple[str, ...]


def leaf_title(row: Row) -> str:
    """Give a leaf card its title, from the row alone.

    Returns:
        The title; the rule is part of it when the row has one, and it is cut to the writer's limit.

    """
    what = f"{row.key} {row.rule}" if row.rule else row.key
    title = f"Ratchet {row.ratchet}: remove the entry {what}"
    return title[:TITLE_LIMIT]


def umbrella_title(ratchet: str) -> str:
    """Give a ratchet's umbrella card its title.

    Returns:
        The title, stable across runs.

    """
    return f"Ratchet {ratchet}: every debt entry removed"[:TITLE_LIMIT]


def plan(rows: list[Row]) -> list[Spec]:
    """Plan the leaf cards and, after them, one umbrella per ratchet.

    Args:
        rows: The census rows, in any order; a row of an unknown value (its key is "unknown") is
            skipped, not planned.

    Returns:
        The leaves in row order, then each umbrella in ratchet order with the titles of its leaves.

    """
    leaves: list[Spec] = []
    under: dict[str, list[str]] = {}
    seen: set[str] = set()
    for row in rows:
        if row.key == UNKNOWN:
            continue
        title = leaf_title(row)
        if title in seen:
            continue
        seen.add(title)
        leaves.append(Spec(title, (row.file,) if row.file else (), ()))
        under.setdefault(row.ratchet, []).append(title)
    umbrellas = [
        Spec(umbrella_title(ratchet), (ratchet,), tuple(titles))
        for ratchet, titles in sorted(under.items())
    ]
    return leaves + umbrellas
