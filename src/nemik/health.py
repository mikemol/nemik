"""nemik:W317: repo health, red / amber / green, from declared thresholds.

Three signals per repo, each read live from the graph: the share of its open cards that are blocked, how
many loop ticks its longest-blocked card has waited (`ticks_blocked`), and how many needs-you operator
asks it holds. `[health]` in rank-weights.toml declares an `[amber, red]` pair for each; a repo is as
unhealthy as its worst signal, and the verdict names every signal that crossed a threshold.
"""

from __future__ import annotations

import tomllib
from importlib.resources import files
from typing import NamedTuple

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM
from nemik.blocks import operator_asks, ref

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
    open_cards = [
        n
        for n in g.subjects(OSLC_CM.state, None)
        if (n, OSLC_CM.state, NEMIK.Done) not in g and ref(n).partition(":")[0] == repo
    ]
    blocked = [n for n in open_cards if (n, OSLC_CM.state, NEMIK.Blocked) in g]
    share = len(blocked) / len(open_cards) if open_cards else 0.0
    ticks = max(
        (int(str(g.value(n, NEMIK.ticksBlocked) or 0)) for n in blocked), default=0
    )
    owed = sum(
        1
        for ask in operator_asks(g)
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
