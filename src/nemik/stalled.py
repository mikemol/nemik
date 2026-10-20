# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W616, W617, W682: a working card that looks stalled, or whose progress is invisible.

el-openglo:W558 sat `working` for a day with no children while about twenty commits landed under
it (operator 2026-10-17: "it looks stalled, and I'm not seeing any predictive power").
Two readings of the same two facts, a card's last_worked time and the commits that cite it with a
`Waypoint:` trailer:
- STALLED: its last activity is older than the repo's learned land interval (the median gap between
  its cited commits, times FACTOR) and no commit has cited it since;
- PROGRESS INVISIBLE: the same staleness, yet commits citing it keep landing: the work moves but the
  card does not show it, so atomize it into children that do.
A card that a queued or gating commit stack names (mikemol-commit --in-gate) is never either: it is
in the gate, whatever the gate's length.
"""

from datetime import datetime
from pathlib import Path

from rdflib import Graph

from nemik import history
from nemik.adapter import NEMIK, OSLC_CM
from nemik.blocks import ref
from nemik.work import in_gate

# A card is stale after this many land intervals without activity: one interval alone would flag
# every card worked an hour ago in a repo that lands every twenty minutes.
FACTOR = 4


def verdict(now: int, worked: int, cites: list[int], interval: int) -> str:
    """Judge a working card from its last activity and the commits that cite it.

    Args:
        now: The current time in epoch seconds.
        worked: When the card was last worked, epoch seconds.
        cites: The epoch seconds of the commits that cite the card.
        interval: The repo's learned land interval, in seconds.

    Returns:
        "ok" while the card is fresh, "stalled" when stale and uncited since, "invisible" when stale
        yet commits citing it have landed since its last activity.

    """
    if now - worked <= FACTOR * interval:
        return "ok"
    return "invisible" if [c for c in cites if c > worked] else "stalled"


def text(said: str, idle: int, interval: int) -> str:
    """Word a warning.

    Args:
        said: "stalled" or "invisible".
        idle: Seconds since the card's last activity.
        interval: The repo's land interval, in seconds.

    Returns:
        The warning text, with the remedy.

    """
    hours = idle // 3600
    pace = f"{hours} h since it was last worked, against a land interval of {interval // 60} min"
    if said == "invisible":
        return (
            f"working, but {pace}, while commits citing it keep landing: progress is invisible; "
            "atomize it into child cards that show each slice (--add ... --enables)"
        )
    return (
        f"working, but {pace}, and no commit cites it since: it looks stalled; work it, "
        "return it to ready, or block it on what it waits for"
    )


def findings(root: Path, merged: Graph, now: int) -> dict[str, list[tuple[str, str]]]:
    """Judge every working card in every repo whose history is readable.

    Args:
        root: The directory holding the repos.
        merged: The merged queue graph.
        now: The current time in epoch seconds.

    Returns:
        (symbol, warning text) pairs by repo; a repo without git history or without a learned land
        interval yields none, and a card in the commit gate is left out.

    """
    found: dict[str, list[tuple[str, str]]] = {}
    intervals: dict[str, int | None] = {}
    gated: dict[str, set[str]] = {}
    for node in merged.subjects(OSLC_CM.state, NEMIK.Working):
        stamp = merged.value(node, NEMIK.lastWorked)
        repo, _, symbol = ref(node).partition(":")
        if stamp is None:
            continue
        if repo not in intervals:
            intervals[repo] = history.land_interval(root / repo)
            gated[repo] = in_gate(root / repo)
        if symbol in gated[repo]:
            continue
        interval = intervals[repo]
        cites = history.citing_epochs(root / repo, symbol)
        if interval is None or cites is None:
            continue
        worked = int(datetime.fromisoformat(str(stamp)).timestamp())
        said = verdict(now, worked, cites, interval)
        if said != "ok":
            found.setdefault(repo, []).append(
                (symbol, text(said, now - worked, interval))
            )
    return found
