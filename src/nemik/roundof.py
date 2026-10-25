# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1024: the next round of a repo: its top N ready cards by rank, N from capacity.

The operator's diagnosis (host 695f3e0a line 95318): the ranking gets ignored and readied cards are
not pursued concurrently, so a session completes a card, takes the one it unblocked, and repeats
down a hot chain while fresh cards get worked and aged cards do not. A round is fixed at one moment:
the best N ready cards by rank, all of them worked together in one stack. A card that becomes ready
afterwards is not in this round; it enters at its rank position when the next round is drawn.

N is not typed. It is what a stack of this repo has carried, the median number of cards a landed
stack held over its recent landings, and one when there is no history. Plain strings and integers
only, no import, so the Codon census compiles it.
"""

NO_HISTORY = "none"
LANDINGS = "landings"


def stack_sizes(gate_seconds: list[str]) -> list[int]:
    """Count the cards of each landed stack from the landing series.

    A stack of several commits is one gate run, so its landings carry the same gate seconds; a run
    of equal values is one stack.

    Args:
        gate_seconds: The gate seconds of a repo's landings, oldest first.

    Returns:
        The size of each run of equal values, oldest first.

    """
    sizes: list[int] = []
    previous = ""
    for seconds in gate_seconds:
        if sizes and seconds == previous:
            sizes[-1] += 1
        else:
            sizes.append(1)
        previous = seconds
    return sizes


def capacity(sizes: list[int]) -> tuple[int, str]:
    """Learn how many cards one round can hold from the stacks that landed.

    Args:
        sizes: The number of cards in each recently landed stack of the repo.

    Returns:
        (the median size rounded up, never below one; where it came from: landings, or none when
        there is no history and the round is one card).

    """
    held = sorted(s for s in sizes if s > 0)
    if not held:
        return 1, NO_HISTORY
    middle = (len(held) + 1) // 2
    return held[middle - 1], LANDINGS


def round_of(ranked: list[tuple[str, str]], size: int) -> list[tuple[str, int, str]]:
    """Take the top of a ranking as the round.

    Args:
        ranked: The ready cards best first, each as (symbol, salience as text).
        size: How many cards the round holds.

    Returns:
        (symbol, rank from 1, salience) for the first `size` cards, in rank order.

    """
    return [
        (symbol, place, salience)
        for place, (symbol, salience) in enumerate(ranked[: max(size, 0)], start=1)
    ]


def outside(working: list[str], in_round: list[str]) -> list[str]:
    """Name the working cards that are not in the round.

    Args:
        working: The repo's cards being worked.
        in_round: The symbols of the round.

    Returns:
        The working cards missing from the round, in the order given.

    """
    held = set(in_round)
    return [card for card in working if card not in held]


def drift(working: list[str], in_round: list[str]) -> tuple[int, int]:
    """Measure how much of the working set lies outside the round.

    Args:
        working: The repo's cards being worked.
        in_round: The symbols of the round.

    Returns:
        (the working cards outside the round, the working cards), a share the caller divides; both
        0 when nothing is being worked.

    """
    return len(outside(working, in_round)), len(working)
