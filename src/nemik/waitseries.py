# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""waitseries: the cross-repo wait edges as series samples, over plain data (nemik:W836, W579).

Operator bar (2026-10-16, via github-8f): the cross-repo wait is a measured quantity with bounded
labels, not a tick count in prose. A row is (waiting repo, blocking repo, ticks the waiting card has
been blocked); a sample is one waiting-and-blocking pair with its oldest wait and how many cards
wait. The labels are the two repos only: a card symbol is never a label (it would multiply the
series), so which card is oldest goes in a log record, not here. Pure functions over lists, with no
import, so the module compiles under Codon as written.
"""

Row = tuple[str, str, int]  # (waiting repo, blocking repo, ticks blocked)


class WaitSample:
    """One waiting-and-blocking pair of repos with the age of its oldest wait and how many wait."""

    waiter: str
    blocker: str
    oldest: int
    count: int

    def __init__(self, waiter: str, blocker: str, oldest: int, count: int) -> None:
        """Hold the two repos, the oldest wait in loop ticks and the number of waiting cards."""
        self.waiter = waiter
        self.blocker = blocker
        self.oldest = oldest
        self.count = count


def samples(rows: list[Row]) -> list[WaitSample]:
    """Group wait rows by the pair of repos, keeping the oldest wait and a count.

    Args:
        rows: One (waiting repo, blocking repo, ticks blocked) per waiting card.

    Returns:
        One sample per pair, oldest wait first, ties by the pair's names.

    """
    oldest: dict[str, int] = {}
    count: dict[str, int] = {}
    for waiter, blocker, ticks in rows:
        key = f"{waiter}\t{blocker}"
        oldest[key] = max(oldest.get(key, 0), ticks)
        count[key] = count.get(key, 0) + 1
    out: list[WaitSample] = []
    for key, age in oldest.items():
        waiter, _, blocker = key.partition("\t")
        out.append(WaitSample(waiter, blocker, age, count[key]))
    return sorted(out, key=_order)


def _order(sample: WaitSample) -> tuple[int, str, str]:
    """Sort key: the oldest wait first, then the repos by name.

    Returns:
        (negated age, waiting repo, blocking repo).

    """
    return (-sample.oldest, sample.waiter, sample.blocker)
