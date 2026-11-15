# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1997: a blocker that keeps landing is a rolling blocker; a card on it never clears.

mtools:W2219 was one rolling card over about 45 entries: it landed 58 times while a second card
waited on it, and nothing could say which entry mattered. A card waiting on an open card that has
landed more than the fleet's own distribution says a card lands before it closes is told to split
the blocker. The bound is learned, a declared percentile of landings per card, never a typed number.

Pure: builtin types only, so the Codon census compiles it. Reading the landings document is
nemik.landings; reading the waiting edges is nemik.check.
"""


def counts(landings: list[tuple[str, str]]) -> dict[str, int]:
    """Count each card's landings.

    Args:
        landings: One (repo, card) per landing; a landing naming no card ("-") is not counted.

    Returns:
        {"repo:card": how many landings named it}.

    """
    found: dict[str, int] = {}
    for repo, card in landings:
        if card == "-":
            continue
        key = f"{repo}:{card}"
        found[key] = found.get(key, 0) + 1
    return found


def bound(landed: dict[str, int], percent: int) -> int:
    """Learn the landings per card that `percent` of cards stay within.

    Args:
        landed: Landings per card, from `counts`.
        percent: The declared percentile, 1 to 100.

    Returns:
        The nearest-rank percentile of the per-card counts; 0 when there are no cards, so a fleet
        with no landings flags nothing it could not measure.

    """
    values = sorted(landed.values())
    if not values:
        return 0
    rank = -(-percent * len(values) // 100)
    return values[max(0, min(len(values), rank) - 1)]


def message(blocker: str, landings: int, limit: int, percent: int) -> str:
    """Word the Warning on a card waiting on a rolling blocker.

    Returns:
        The text, naming the blocker, its landings and the learned bound.

    """
    return (
        f"blocked on {blocker}, which has landed {landings} commits (the {percent}th percentile "
        f"of landings per card is {limit}): a blocker that keeps landing never clears, so split "
        "it into cards that can close, or wait on the part you need"
    )
