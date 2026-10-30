# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W326: starvation, the failure of a pure priority queue.

A ready card is STARVED when it has waited longer than the declared age (`[starvation] days` in
rank-weights.toml) while cards issued after it were ranked above it. Ranking by band and flow
salience never ages a card, so a low-weight card can sit behind a stream of newer, heavier ones
forever. This
reports who is overtaken and by how many; whether to add an aging term to the order is a separate,
declared decision (the residue term is off by default for the same reason: measure first).
"""

from __future__ import annotations

import argparse
import json
import tomllib
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import NamedTuple

from rdflib import Graph
from rdflib.namespace import DCTERMS

from nemik.adapter import waypoint_uri
from nemik.rank import fleet_repos, load_composition, load_weights, rank
from nemik.tomlview import table

DEFAULT_DAYS = 14


class Starved(NamedTuple):
    """A ready card that waited past the limit while newer cards ranked above it."""

    cite: str
    waited_days: float
    overtaken_by: int


def days_limit(text: str | None = None) -> int:
    """Read the declared age in days (`[starvation] days`), or 14 when the table is absent.

    Returns:
        The number of days.

    """
    if text is None:
        text = files("nemik.data").joinpath("rank-weights.toml").read_text()
    section = table(table(tomllib.loads(text)).get("starvation"))
    return int(str(section.get("days", DEFAULT_DAYS)))


def starved(
    g: Graph, repo: str, now: datetime, days: int = DEFAULT_DAYS
) -> list[Starved]:
    """`repo`'s ready cards that waited over `days` while later-issued cards ranked above them.

    Returns:
        The starved cards, longest wait first.

    """
    order = rank(g, repo, load_weights(), load_composition())
    symbols = [str(row["symbol"]) for row in order]
    issued: dict[str, datetime] = {}
    for symbol in symbols:
        stamp = g.value(waypoint_uri(repo, symbol), DCTERMS.created)
        if stamp is not None:
            issued[symbol] = datetime.fromisoformat(str(stamp))
    found: list[Starved] = []
    for i, symbol in enumerate(symbols):
        born = issued.get(symbol)
        if born is None or (now - born).days <= days:
            continue
        ahead = [s for s in symbols[:i] if issued.get(s, born) > born]
        if ahead:
            found.append(
                Starved(
                    f"{repo}:{symbol}",
                    round((now - born).total_seconds() / 86400, 1),
                    len(ahead),
                )
            )
    return sorted(found, key=lambda s: -s.waited_days)


def starved_fleet(
    g: Graph, repos: list[str], now: datetime, days: int = DEFAULT_DAYS
) -> list[Starved]:
    """`starved` over the given repos, or every repo of the graph when none is given.

    Returns:
        Each repo's starved cards, one repo after another.

    """
    found: list[Starved] = []
    for repo in repos or fleet_repos(g):
        found += starved(g, repo, now, days)
    return found


class Options(argparse.Namespace):
    """The parsed command line of nemik-starved (nemik:W1187)."""

    repos: list[str]
    root: Path
    days: int | None
    json: bool


def main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """nemik-starved: ready cards overtaken by newer ones for longer than the declared age."""
    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(
        prog="nemik-starved", description=(main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument("repos", nargs="*", help="only these repos (default: every one)")
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github")
    ap.add_argument(
        "--days", type=int, default=None, help="age limit (default: the declared)"
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv, namespace=Options())
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    days = args.days if args.days is not None else days_limit()
    now = datetime.now(UTC)
    found = starved_fleet(g, args.repos, now, days)
    if args.json:
        print(json.dumps([s._asdict() for s in found], indent=1))
        return
    print(
        f"starved ready cards (waited over {days} days, overtaken by newer ones): {len(found)}"
    )
    for s in found:
        print(f"  {s.cite}  waited {s.waited_days}d, overtaken by {s.overtaken_by}")
