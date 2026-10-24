# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W992: cards that languish behind a grooming umbrella.

luthen's restart-safety chain sat for 140 ticks blocked only on W1285, an umbrella whose work was
atomizing ready cards (github:W37, finding F9). A card parked behind a grooming umbrella reads as
blocked, so no ranking surfaces it. A card languishes when its only blockers are grooming
umbrellas and it has been blocked longer than a learned tick count: the 90th percentile (nearest
rank) of the ticks cards have spent blocked on real work, so the bound is the repo's own
experience of how long a real block takes, not a typed number (the repo's rule for thresholds).
Plain strings and integers only, no import, so the Codon census compiles it.
"""

PERCENTILE = 90
MINIMUM_BOUND = 1


def learned_bound(ticks_on_real_work: list[int]) -> int:
    """Learn how many blocked ticks is long for a card waiting on real work.

    Args:
        ticks_on_real_work: The ticks_blocked of each blocked card that waits on something other
            than a grooming umbrella.

    Returns:
        The 90th percentile by nearest rank, never below one; one when there is no history.

    """
    if not ticks_on_real_work:
        return MINIMUM_BOUND
    ordered = sorted(ticks_on_real_work)
    rank = -(-len(ordered) * PERCENTILE // 100)
    return max(MINIMUM_BOUND, ordered[max(0, rank - 1)])


def _longest_first(row: tuple[str, int, str]) -> tuple[int, str]:
    """Order rows by ticks, most first, then by card name.

    Returns:
        The sort key.

    """
    return -row[1], row[0]


def languishing(
    blocked: dict[str, tuple[int, list[str]]], grooming: list[str]
) -> list[tuple[str, int, str]]:
    """Find the cards parked behind a grooming umbrella past the learned bound.

    Args:
        blocked: Each blocked card and its ticks_blocked and the cards it waits for.
        grooming: The umbrellas whose work is giving other cards manifests.

    Returns:
        (card, ticks blocked, the grooming umbrella it waits on) for each card whose only blockers
        are grooming umbrellas and whose ticks exceed the bound, longest-waiting first.

    """
    umbrellas = set(grooming)
    real = [
        ticks
        for ticks, waits in blocked.values()
        if waits and any(w not in umbrellas for w in waits)
    ]
    bound = learned_bound(real)
    found = [
        (card, ticks, min(waits))
        for card, (ticks, waits) in blocked.items()
        if waits and all(w in umbrellas for w in waits) and ticks > bound
    ]
    return sorted(found, key=_longest_first)
