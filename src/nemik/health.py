"""nemik:W317: repo health, red / amber / green, from declared thresholds.

Three signals per repo, each read live from the graph: the share of its open cards that are blocked, how
many loop ticks its longest-blocked card has waited (`ticks_blocked`), and how many needs-you operator
asks it holds. `[health]` in rank-weights.toml declares an `[amber, red]` pair for each; a repo is as
unhealthy as its worst signal, and the verdict names every signal that crossed a threshold.
"""

from __future__ import annotations

import tomllib
from importlib.resources import files
from typing import Any, NamedTuple

from rdflib import Graph

from nemik.blocks import operator_asks
from nemik.cards import Card, cards

STATUSES = ("green", "amber", "red")
SIGNALS = ("blocked_share", "oldest_block_ticks", "asks_owed")


class Health(NamedTuple):
    status: str
    blocked_share: float
    oldest_block_ticks: int
    asks_owed: int
    reasons: list[str]


def thresholds(text: str | None = None) -> dict[str, tuple[float, float]]:
    """The declared `[health]` table: for each signal, its (amber, red) floor."""
    if text is None:
        text = files("nemik.data").joinpath("rank-weights.toml").read_text()
    table = tomllib.loads(text).get("health", {})
    return {s: (float(table[s][0]), float(table[s][1])) for s in SIGNALS if s in table}


def health(g: Graph, repo: str, limits: dict[str, tuple[float, float]]) -> Health:
    """`repo`'s verdict: the worst of its signals against `limits`, with a reason per crossing."""
    return health_cards(cards(g), operator_asks(g), repo, limits)


def health_cards(
    by_cite: dict[str, Card],
    asks: list[dict[str, Any]],
    repo: str,
    limits: dict[str, tuple[float, float]],
) -> Health:
    """nemik:W454: `health` over plain Cards and the operator asks as plain rows: the portable core."""
    open_cards = [c for c in by_cite.values() if not c.done and c.repo == repo]
    blocked = [c for c in open_cards if c.state == "blocked"]
    share = len(blocked) / len(open_cards) if open_cards else 0.0
    ticks = max((c.ticks_blocked for c in blocked), default=0)
    owed = sum(
        1
        for ask in asks
        if ask["category"] == "needs-you" and str(ask["ref"]).partition(":")[0] == repo
    )
    seen = {"blocked_share": share, "oldest_block_ticks": ticks, "asks_owed": owed}
    worst, reasons = 0, []
    for signal, value in seen.items():
        amber, red = limits.get(signal, (float("inf"), float("inf")))
        level = 2 if value >= red else 1 if value >= amber else 0
        if level:
            floor = red if level == 2 else amber
            reasons.append(f"{signal} {value:g} (>= {floor:g}: {STATUSES[level]})")
        worst = max(worst, level)
    return Health(STATUSES[worst], round(share, 3), ticks, owed, reasons)
