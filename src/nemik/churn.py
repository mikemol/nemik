# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W495: how often a poll of the fleet's graph finds it changed, and how, walked from git history.

The view polls every 60 s and redraws from scratch whenever the graph text differs. Whether to patch
in place instead depends on WHAT changes between polls: a card's attributes (patchable where it
stands), a status flip (a recolour), or the drawn structure itself (cards or edges added or
removed). Two live snapshots minutes apart say nothing when the fleet is quiet, so this walks
history: each repo's committed queue is sampled at fixed steps over a span, every repo that moved in
an interval is classified, and the interval takes the worst class among them.

History is commit-granular and the live view also sees uncommitted queue writes, so every share here
is a floor on how often the view changes, never a ceiling.
"""

from __future__ import annotations

import bisect
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from nemik.history import Snapshot, diff, queue_at, resolve, snapshots

if TYPE_CHECKING:
    from pathlib import Path

# Ordered mildest first: an interval is as bad as the worst repo in it.
CLASSES = ("identical", "attribute", "state", "structural")
STEPS = (60, 300, 3600)  # seconds: the poll, five of them, an hour


def classify(old: dict, new: dict) -> str:
    """How the drawn graph must change to follow `old` -> `new`, two parsed queues.

    structural: a card minted, closed (done leaves the default view) or dropped, or an edge added or
    removed; state: only status flips among open cards; attribute: any other change to a card;
    identical: nothing a card shows moved (the lock, heartbeat and counter are not drawn).
    """
    d = diff(old, new)
    if d.minted or d.closed or d.dropped or d.edges_added or d.edges_removed:
        return "structural"
    if d.flips:
        return "state"
    if old.get("waypoints") != new.get("waypoints"):
        return "attribute"
    return "identical"


@dataclass(frozen=True)
class Churn:
    """One poll step over the span: how many polls, and how many found each class of change."""

    step: int
    polls: int
    counts: dict[str, int]

    def share(self, cls: str) -> float:
        """Measure how much of the polling a change class took.

        Returns:
            The class's count over all polls, 0.0 when there were none.

        """
        return self.counts.get(cls, 0) / self.polls if self.polls else 0.0

    def redraws_now(self) -> float:
        """Today every change redraws everything."""
        return 1.0 - self.share("identical")

    def redraws_patching_attributes(self) -> float:
        """Patching attributes and recolours in place leaves only structure to redraw."""
        return self.share("structural")


def _times(snaps: list[Snapshot]) -> list[datetime]:
    return [at for at, _ in snaps]


def _state(snaps: list[Snapshot], when: datetime) -> dict:
    """The queue as it stood at `when`: the last commit at or before it."""
    at = bisect.bisect_right(_times(snaps), when)
    return snaps[at - 1][1] if at else {}


def churn(
    fleet: dict[str, list[Snapshot]], start: datetime, end: datetime, step: int
) -> Churn:
    """Classify every `step`-second poll in [start, end): compare each moved repo's queue at the
    poll's two ends, and count the interval under its worst class.
    """
    counts: Counter[str] = Counter()
    times = {repo: _times(snaps) for repo, snaps in fleet.items()}
    polls, at = 0, start
    while at + timedelta(seconds=step) <= end:
        nxt = at + timedelta(seconds=step)
        worst = 0
        for repo, snaps in fleet.items():
            held = times[repo]
            if bisect.bisect_right(held, nxt) == bisect.bisect_right(held, at):
                continue  # no commit landed in this interval
            cls = classify(_state(snaps, at), _state(snaps, nxt))
            worst = max(worst, CLASSES.index(cls))
        counts[CLASSES[worst]] += 1
        polls += 1
        at = nxt
    return Churn(step, polls, dict(counts))


def commit_classes(
    fleet: dict[str, list[Snapshot]], start: datetime, end: datetime
) -> dict[str, int]:
    """What each commit in the span did, by class, independent of any poll step."""
    out: Counter[str] = Counter()
    for snaps in fleet.values():
        for i in range(1, len(snaps)):
            if start < snaps[i][0] <= end:
                out[classify(snaps[i - 1][1], snaps[i][1])] += 1
    return dict(out)


def sample(repo: Path, since: str, start: datetime) -> list[Snapshot]:
    """The repo's queue at the span's start, then every commit after it."""
    base = queue_at(repo, resolve(repo, since))
    return [(start, base), *snapshots(repo, since, full=True)]


def render(
    span: tuple[datetime, datetime],
    repos: int,
    commits: dict[str, int],
    rows: list[Churn],
) -> str:
    """Print the churn report.

    Args:
        span: The first and last time covered.
        repos: How many repos were read.
        commits: Commits by change class.
        rows: The churn rows to report.

    Returns:
        The report text.

    """
    start, end = span
    total = sum(commits.values())
    head = f"queue churn {start:%Y-%m-%d %H:%M} .. {end:%Y-%m-%d %H:%M}, {repos} repos"
    floor = "a floor: history is commit-granular, the live view also sees uncommitted writes"
    by_class = ", ".join(f"{c} {commits.get(c, 0) / total:.0%}" for c in CLASSES[1:])
    lines = [
        f"{head}; {floor}",
        f"{total} commits: {by_class}" if total else "no commits in the span",
    ]
    for row in rows:
        shares = ", ".join(f"{c} {row.share(c):.1%}" for c in CLASSES)
        lines.append(f"polls every {row.step:>4} s ({row.polls}): {shares}")
        lines.append(
            f"    redrawn now {row.redraws_now():.1%}; "
            f"redrawn if attributes and recolours patch in place {row.redraws_patching_attributes():.1%}"
        )
    return "\n".join(lines)


def run(
    dirs: dict[str, Path], names: list[str], since: str | None, as_json: bool
) -> int:
    """nemik-history --churn: walk the span's history and report how a poll finds the fleet."""
    end = datetime.now(UTC)
    when = since or (end - timedelta(days=7)).strftime("%Y-%m-%d")
    start = datetime.fromisoformat(when)
    start = start if start.tzinfo else start.replace(tzinfo=UTC)
    fleet = {name: sample(dirs[name], when, start) for name in names}
    rows = [churn(fleet, start, end, step) for step in STEPS]
    commits = commit_classes(fleet, start, end)
    if as_json:
        out = {"commits": commits, "polls": [asdict(r) for r in rows]}
        print(json.dumps(out, indent=1))
    else:
        print(render((start, end), len(names), commits, rows))
    return 0
