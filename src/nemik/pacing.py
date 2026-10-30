# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W327: arrival pacing, a token bucket over each repo's new cards.

A repo may mint cards at a declared rate per day with a declared burst on top (`[pacing]` in
rank-weights.toml). The bucket starts full at `burst`, refills at `rate` per day up to `burst`,
and each new card (its `issued_at`) takes one token. When the bucket goes negative the repo is
minting faster than its pace; the deepest it went over the window is the overdraft. This only
REPORTS: whether to
enforce a pace is a separate decision (the doc's "advisory first").
"""

from __future__ import annotations

import argparse
import tomllib
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import NamedTuple

from rdflib import Graph
from rdflib.namespace import DCTERMS

from nemik.blocks import ref


class Pace(NamedTuple):
    """One repo's token bucket after its window of new cards."""

    repo: str
    arrivals: int  # new cards in the window
    overdraft: float  # how far below zero the bucket went (0 when it never did)
    level: float  # tokens left now


def limits(text: str | None = None) -> tuple[float, float, int]:
    """Read the declared (rate per day, burst, window days); 50, 150, 14 if the table is absent.

    Returns:
        The declared (rate per day, burst, window days), or (50, 150, 14) for any
        key the table lacks.

    """
    if text is None:
        text = files("nemik.data").joinpath("rank-weights.toml").read_text()
    t: dict[str, float] = tomllib.loads(text).get("pacing", {})
    return (
        float(t.get("rate", 50)),
        float(t.get("burst", 150)),
        int(t.get("window_days", 14)),
    )


def bucket(
    stamps: list[datetime], rate: float, burst: float, start: datetime, now: datetime
) -> tuple[float, float]:
    """(overdraft, level now) for arrivals `stamps` from `start` to `now`.

    Returns:
        The overdraft (how far below zero the bucket went, 0 when it never did)
        and the level now, each rounded to one decimal.

    """
    level, worst, at = burst, 0.0, start
    for t in sorted(s for s in stamps if start <= s <= now):
        level = min(burst, level + rate * (t - at).total_seconds() / 86400)
        at = t
        level -= 1
        worst = min(worst, level)
    level = min(burst, level + rate * (now - at).total_seconds() / 86400)
    return round(max(0.0, -worst), 1), round(level, 1)


def paces(g: Graph, now: datetime, rate: float, burst: float, days: int) -> list[Pace]:
    """Every repo's pace over the last `days` days, the most over first.

    Returns:
        One Pace per repo that has a created card, sorted by overdraft descending, then repo.

    """
    start = now - timedelta(days=days)
    stamps: dict[str, list[datetime]] = {}
    for node, _, stamp in g.triples((None, DCTERMS.created, None)):
        try:
            at = datetime.fromisoformat(str(stamp))
        except ValueError:
            continue
        stamps.setdefault(ref(node).partition(":")[0], []).append(at)
    out = []
    for repo, seen in stamps.items():
        overdraft, level = bucket(seen, rate, burst, start, now)
        arrivals = sum(1 for s in seen if start <= s <= now)
        out.append(Pace(repo, arrivals, overdraft, level))
    return sorted(out, key=lambda p: (-p.overdraft, p.repo))


def main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """nemik-pacing: each repo's new cards against a declared rate and burst (a token bucket)."""
    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(
        prog="nemik-pacing", description=(main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github")
    args = ap.parse_args(argv)
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    rate, burst, days = limits()
    print(f"pace: {rate:g} new cards a day, burst {burst:g}, over the last {days} days")
    for p in paces(g, datetime.now(UTC), rate, burst, days):
        flag = "  OVER PACE NOW" if p.level < 0 else ""
        print(
            f"  {p.repo:22} {p.arrivals:4} new, went {p.overdraft:g} over, "
            f"{p.level:g} tokens left{flag}"
        )
