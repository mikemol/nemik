# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""ratchet_atomizer: the plan of cards for any ratchet's debt rows (nemik:W1994).

The design is in docs/ratchet-atomizer.md. A row is (ratchet, key, file, rule). The plan is one
umbrella card per ratchet and one leaf card per KEY of it (a file, or a module); the rules or modes
the key owes are listed in the leaf, not made leaves of their own, because one file is one edit
cone (a dry run of the codon baseline gave 122 rows for 61 modules, two leaves sharing each manifest
file). An umbrella waits on its leaves. A title is a function of the key and its rules alone, so a
second run finds each card again. This module only plans: it reads no file, writes no queue, and
imports only the standard library.
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


def leaf_title(ratchet: str, key: str, rules: tuple[str, ...]) -> str:
    """Give a leaf card its title, from the ratchet, the key and the rules it owes alone.

    Returns:
        The title; the rules are part of it when the key has any, and it is cut to the writer's
        limit.

    """
    what = f"{key} ({', '.join(rules)})" if rules else key
    title = f"Ratchet {ratchet}: remove the entries of {what}"
    return title[:TITLE_LIMIT]


def umbrella_title(ratchet: str) -> str:
    """Give a ratchet's umbrella card its title.

    Returns:
        The title, stable across runs.

    """
    return f"Ratchet {ratchet}: every debt entry removed"[:TITLE_LIMIT]


def plan(rows: list[Row]) -> list[Spec]:
    """Plan one leaf card per key and, after them, one umbrella per ratchet.

    Args:
        rows: The census rows, in any order; a row of an unknown value (its key is "unknown") is
            skipped, not planned. Rows of one key become one leaf, their rules listed sorted.

    Returns:
        The leaves in first-seen key order, then each umbrella in ratchet order with the titles
        of its leaves.

    """
    files: dict[tuple[str, str], str] = {}
    rules: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        if row.key == UNKNOWN:
            continue
        which = (row.ratchet, row.key)
        files[which] = files.get(which) or row.file
        rules.setdefault(which, set())
        if row.rule:
            rules[which].add(row.rule)
    leaves: list[Spec] = []
    under: dict[str, list[str]] = {}
    for which, file in files.items():
        title = leaf_title(which[0], which[1], tuple(sorted(rules[which])))
        leaves.append(Spec(title, (file,) if file else (), ()))
        under.setdefault(which[0], []).append(title)
    umbrellas = [
        Spec(umbrella_title(ratchet), (ratchet,), tuple(titles))
        for ratchet, titles in sorted(under.items())
    ]
    return leaves + umbrellas
