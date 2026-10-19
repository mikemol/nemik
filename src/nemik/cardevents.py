# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W744: one event per change to a card, the observations of the weather-and-climate series.

A queue file is committed as snapshots; the difference between two snapshots is the changes made
between them. Each change is an event: the station (the card, `repo:W<n>`), the time, the field
that changed, what it was, what it became, and the commit that carried it. Cards are the weather
stations and the repos the regions (nemik:W743). Pure functions over parsed queues: reading git is
`history.backfill`.
"""

# No `from __future__ import annotations`: Codon's as-written census cannot import it, and a new
# module must compile as written.
# station, time, field, from, to, commit
Event = tuple[str, str, str, str, str, str]
Queue = dict[str, list[dict[str, str | list[str]]]]

FIELDS = ("status", "blocked_kind", "blocked_on", "enables")


def _text(value: str | list[str]) -> str:
    """Write one field value as the single string an event carries.

    Returns:
        The string itself, a list joined by commas, or "" for an empty list or a null a queue
        stores for a field that is unset.

    """
    if isinstance(value, str):
        return value
    return ",".join(value) if value else ""


def _states(queue: Queue) -> dict[str, dict[str, str]]:
    """Read each card's tracked fields out of a queue.

    Returns:
        {symbol: {field: text}} for every card in the queue.

    """
    return {
        _text(w["symbol"]): {name: _text(w.get(name, "")) for name in FIELDS}
        for w in queue.get("waypoints", [])
    }


def _dropped(queue: Queue) -> set[str]:
    """Name the cards a queue has moved to residue.

    Returns:
        The residue symbols.

    """
    return {_text(r["symbol"]) for r in queue.get("residue", [])}


def events_of(repo: str, old: Queue, new: Queue, sha: str, stamp: str) -> list[Event]:
    """List what changed between two snapshots of a repo's queue, as events.

    A card new to the queue is `card` from nothing to `minted`; a card that left it is `card` to
    `dropped` when residue holds it, else to `removed`; any other change is one event per tracked
    field, in the order of FIELDS, cards in symbol order.

    Returns:
        The events, none when the two snapshots agree.

    """
    before, after = _states(old), _states(new)
    dropped = _dropped(new)
    out: list[Event] = []
    for symbol in sorted(after):
        station = f"{repo}:{symbol}"
        if symbol not in before:
            out.append((station, stamp, "card", "", "minted", sha))
            continue
        for name in FIELDS:
            was, now = before[symbol][name], after[symbol][name]
            if was != now:
                out.append((station, stamp, name, was, now, sha))
    for symbol in sorted(set(before) - set(after)):
        gone = "dropped" if symbol in dropped else "removed"
        was = before[symbol]["status"]
        out.append((f"{repo}:{symbol}", stamp, "card", was, gone, sha))
    return out
