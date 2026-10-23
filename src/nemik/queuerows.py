# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""queuerows: a repo's ready cards as a queue, in the order they will be worked (nemik:W931, W929).

The operator said (2026-10-23) that the page does not show a repo's queue as a queue: the same ready
cards stay ready for ages while new ones come ready. nemik-rank already gives the order (band, then
flow salience) and nemik-starved already counts, for a card that waited past a bar, how many newer
cards were ranked above it. This gives every ready card both, with no bar: its place, its weight
and band, how long it has waited since it was issued, and how many cards issued after it sit ahead
of it. A card ranked first with no newer card ahead is the head of an honest queue; one with a long
wait and a long list of newer cards ahead is what the operator described.
"""

from datetime import UTC, datetime
from typing import NamedTuple

from rdflib import Graph
from rdflib.namespace import DCTERMS

from nemik.adapter import waypoint_uri
from nemik.rank import fleet_repos, load_composition, load_weights, rank

SECONDS_A_DAY = 86400
UNKNOWN = -1.0


class QueueRow(NamedTuple):
    """One card's place in its repo's queue."""

    place: int
    cite: str
    title: str
    weight: int
    band: str
    waited_days: float
    overtaken_by: int


def _issued(g: Graph, repo: str, symbols: list[str]) -> dict[str, datetime]:
    """Read when each card was issued.

    Returns:
        symbol -> its `dcterms:created` instant; a card with none is left out.

    """
    born: dict[str, datetime] = {}
    for symbol in symbols:
        stamp = g.value(waypoint_uri(repo, symbol), DCTERMS.created)
        if stamp is not None:
            born[symbol] = datetime.fromisoformat(str(stamp))
    return born


def queue_rows(g: Graph, repo: str, now: datetime) -> list[QueueRow]:
    """List a repo's ready cards in work order, with how long each waited and who passed it.

    Args:
        g: The merged queue graph.
        repo: The repo.
        now: The instant waits are measured to.

    Returns:
        One row per ranked card, place 1 first; `waited_days` is UNKNOWN (-1) for a card with no
        issue stamp, and `overtaken_by` counts the cards above it that were issued after it.

    """
    order: list[dict[str, object]] = rank(g, repo, load_weights(), load_composition())
    symbols = [str(row["symbol"]) for row in order]
    born = _issued(g, repo, symbols)
    rows: list[QueueRow] = []
    for index, row in enumerate(order):
        symbol = symbols[index]
        when = born.get(symbol)
        ahead = (
            sum(1 for above in symbols[:index] if above in born and born[above] > when)
            if when is not None
            else 0
        )
        waited = (
            round((now - when).total_seconds() / SECONDS_A_DAY, 1)
            if when is not None
            else UNKNOWN
        )
        rows.append(
            QueueRow(
                index + 1,
                f"{repo}:{symbol}",
                str(row["title"]),
                int(str(row["weight"])),
                str(row["band_name"]),
                waited,
                ahead,
            )
        )
    return rows


def fleet_queues(
    g: Graph, repos: list[str], now: datetime | None = None
) -> dict[str, list[QueueRow]]:
    """Build every named repo's queue, or every repo's when none is named.

    Returns:
        repo -> its queue rows, in work order.

    """
    stamp = now or datetime.now(UTC)
    return {repo: queue_rows(g, repo, stamp) for repo in repos or fleet_repos(g)}
