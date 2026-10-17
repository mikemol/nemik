# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W618: when an umbrella will finish, and which working cards cannot be forecast.

An umbrella is an open card two or more of whose own repo's open cards enable it (its children).
Its forecast is the open children over the repo's recent close rate, in days. A working card with
no children at all has nothing to count, so it is reported as unforecastable, never silently fine
(operator 2026-10-17, el-openglo:W558: a working card with no children and many commits under it).
"""

from datetime import datetime, timedelta
from pathlib import Path

from rdflib import Graph
from rdflib.term import Node

from nemik import history
from nemik.adapter import NEMIK, OSLC_CM
from nemik.blocks import ref
from nemik.check import QUEUE, workstream_files

WINDOW_DAYS = 14  # the close rate is read over this many days
UMBRELLA = 2  # open children that make a card an umbrella


def open_children(merged: Graph, card: Node) -> list[Node]:
    """List a card's open children: cards of its own repo that enable it.

    Args:
        merged: The merged queue graph.
        card: The parent card.

    Returns:
        Its enablers in the same repo whose state is not done.

    """
    repo = ref(card).partition(":")[0]
    return [
        kid
        for kid in merged.subjects(NEMIK.enables, card)
        if ref(kid).partition(":")[0] == repo
        and (kid, OSLC_CM.state, NEMIK.Done) not in merged
    ]


def days_left(children: int, rate: float) -> float | None:
    """Forecast an umbrella's finish.

    Args:
        children: How many open children it has.
        rate: The repo's cards closed per day.

    Returns:
        Days to finish at that rate, or None when nothing has closed (no rate to divide by).

    """
    return children / rate if rate > 0 else None


def summary(merged: Graph, repo: str, rate: float) -> tuple[float | None, int]:
    """Summarize a repo's forecast.

    Args:
        merged: The merged queue graph.
        repo: The repo's name.
        rate: Its close rate per day.

    Returns:
        The slowest umbrella's days left (None when there is none or no rate), and how many of
        its working cards have no children at all.

    """
    slowest: float | None = None
    bare = 0
    for card in merged.subjects(OSLC_CM.state, None):
        if (
            ref(card).partition(":")[0] != repo
            or (card, OSLC_CM.state, NEMIK.Done) in merged
        ):
            continue
        kids = open_children(merged, card)
        left = days_left(len(kids), rate) if len(kids) >= UMBRELLA else None
        if left is not None and (slowest is None or left > slowest):
            slowest = left
        working = (card, OSLC_CM.state, NEMIK.Working) in merged
        if working and not list(merged.subjects(NEMIK.enables, card)):
            bare += 1
    return slowest, bare


def lines(root: Path, merged: Graph, now: datetime) -> list[str]:
    """Print the forecast gauges for every repo with readable history.

    Args:
        root: The fleet root.
        merged: The merged queue graph.
        now: The instant the window ends at.

    Returns:
        TYPE lines for nemik_umbrella_forecast_days and nemik_unforecastable_cards and their
        samples.

    """
    start = (now - timedelta(days=WINDOW_DAYS)).astimezone()
    since = start.strftime("%Y-%m-%dT%H:%M:%S")
    out = [
        "# TYPE nemik_umbrella_forecast_days gauge",
        "# TYPE nemik_unforecastable_cards gauge",
    ]
    for repo, path in workstream_files(root, QUEUE):
        top = path.parents[1] if path.parent.name == ".claude" else path.parent
        rate = history.close_rate(top, since, WINDOW_DAYS)
        if rate is None:
            continue
        slowest, bare = summary(merged, repo, rate)
        if slowest is not None:
            out.append(f'nemik_umbrella_forecast_days{{repo="{repo}"}} {slowest:.1f}')
        out.append(f'nemik_unforecastable_cards{{repo="{repo}"}} {bare}')
    return out
