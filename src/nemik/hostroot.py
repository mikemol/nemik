# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""hostroot: luthen's host-root frontier as rows, newest per resource (nemik:W773, W461).

luthen-observability publishes the root-run host's resources as one log line per node per
refresh (stream host_root_frontier, luthen-observability:W1468). The document is the latest
line per id. This module is the pure part: the row, the choice of the latest row per id, and
whether a row is stale. Reading the stream is nemik:W774; showing it is nemik:W775.
"""

from .climate import _instant

STATES = ["done", "ready", "blocked"]
# luthen refreshes hourly; past two hours without a newer line, the reading is not current
# (the stream has no freshness alert, so as_of is the only evidence).
STALE_HOURS = 2.0
SECONDS_PER_HOUR = 3600.0


class HostRow:
    """One node of the host-root frontier as a line of the stream reported it."""

    def __init__(self, ident: str, state: str, as_of: str) -> None:
        """Hold the identity, state and stamp; the reader sets the rest as it parses."""
        self.ident = ident
        self.state = state
        self.as_of = as_of
        self.waits_for: list[str] = []
        self.gate = ""
        self.reading = ""


def latest(rows: list[HostRow]) -> list[HostRow]:
    """Keep the newest row of each id; a later row wins a tie on as_of.

    Args:
        rows: Every line read from the stream, in the order read.

    Returns:
        One row per id, in the order each id first appeared.

    """
    best: dict[str, HostRow] = {}
    order: list[str] = []
    for row in rows:
        held = best.get(row.ident)
        if held is None:
            order.append(row.ident)
            best[row.ident] = row
        elif row.as_of >= held.as_of:
            best[row.ident] = row
    return [best[ident] for ident in order]


def stale(row: HostRow, now: str) -> bool:
    """Say whether a row's as_of is older than STALE_HOURS before `now`.

    Args:
        row: A row of the frontier.
        now: An ISO stamp.

    Returns:
        True when the row is older than the window, or its stamp cannot be read.

    """
    try:
        age = _instant(now) - _instant(row.as_of)
    except ValueError:
        return True
    return age.total_seconds() > STALE_HOURS * SECONDS_PER_HOUR
