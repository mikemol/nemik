# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W745: the weather, each card's current state folded out of its events.

The events (nemik:W744) say what changed and when; the weather is where each station stands now:
its status and since when, what kind of block it is under, and what it waits on. Rank weight and
manifest size are not events and come from the queue and the rank, not from here.
"""

# No `from __future__ import annotations` (Codon's as-written census cannot import it) and no
# typing.TYPE_CHECKING: the event type is spelled here, as nemik.cardevents.Event, so this module
# imports nothing and compiles under Codon as written.
# station, time, field, from, to, commit
Event = tuple[str, str, str, str, str, str]

FIELDS = ("status", "status_since", "blocked_kind", "blocked_on")
BLOCK_FIELDS = {"blocked_kind", "blocked_on"}


def weather_of(events: list[Event]) -> dict[str, dict[str, str]]:
    """Fold events, oldest first, into the current state of each station.

    A card minted starts with no status; a `status` event sets the status and the time it began; a
    card dropped or removed ends with that as its status; blocked_kind and blocked_on follow their
    events. Changes to `enables` do not touch the weather.

    Returns:
        {station: {"status", "status_since", "blocked_kind", "blocked_on"}}.

    """
    out: dict[str, dict[str, str]] = {}
    for station, at, field, _, now, _ in events:
        state = out.setdefault(station, dict.fromkeys(FIELDS, ""))
        if field == "card":
            state["status"] = "" if now == "minted" else now
            state["status_since"] = at
        elif field == "status":
            state["status"] = now
            state["status_since"] = at
        elif field in BLOCK_FIELDS:
            state[field] = now
    return out
