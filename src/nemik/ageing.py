# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1001: a ready card's rank rises with its age past how long small cards take to finish.

The operator saw the same band of ready cards a week old (host 695f3e0a line 94134), after saying
that difficult commitments languish (line 93549). nemik-rank had no aging term, by choice
(rank-weights.toml [starvation]), so a fresh interrupt of weight 900 outranked a weight-1 card
forever. The bound is learned, not typed: the 90th percentile, by nearest rank, of the seconds
finished small cards took from issue to completion, with none learned from fewer than ten. A card
is overdue by the whole bounds its age holds beyond the first two: it is untouched for more than
one bound when nemik-check warns, and it starts to outrank fresh work after a second one, so the
slope is the bound itself and no constant is typed here. Integers only, no import, so the Codon
census compiles it.
"""

PERCENTILE = 90
MIN_SAMPLES = 10
NO_BOUND = -1
# whole bounds a ready card may age before it starts to outrank fresh work
GRACE_BOUNDS = 2


def learned_bound(spans: list[int]) -> int:
    """Learn how long a small card takes to finish.

    Args:
        spans: The seconds from issue to completion of each finished small card.

    Returns:
        The 90th percentile by nearest rank, or NO_BOUND under ten spans or when it is not above
        zero.

    """
    if len(spans) < MIN_SAMPLES:
        return NO_BOUND
    ordered = sorted(spans)
    rank = -(-len(ordered) * PERCENTILE // 100)
    got = ordered[max(0, rank - 1)]
    return got if got > 0 else NO_BOUND


def overdue(age: int, bound: int) -> int:
    """Count the whole bounds a ready card has aged beyond its grace.

    Args:
        age: Seconds since the card was last issued or worked.
        bound: The learned bound in seconds, or NO_BOUND.

    Returns:
        0 while the card is within two bounds or no bound is learned, else the whole bounds in its
        age less one, so it is 1 at two bounds and rises by one per further bound.

    """
    if bound <= 0 or age < GRACE_BOUNDS * bound:
        return 0
    return age // bound - 1
