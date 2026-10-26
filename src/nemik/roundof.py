# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1024: the next round of a repo: its top N ready cards by rank, N from capacity.

The operator's diagnosis (host 695f3e0a line 95318): the ranking gets ignored and readied cards are
not pursued concurrently, so a session completes a card, takes the one it unblocked, and repeats
down a hot chain while fresh cards get worked and aged cards do not. A round is fixed at one moment:
the best N ready cards by rank, all of them worked together in one stack. A card that becomes ready
afterwards is not in this round; it enters at its rank position when the next round is drawn.

N is not typed. It is what a stack of this repo has carried, the median number of cards a landed
stack held over its recent landings, lifted to FLOOR where that is smaller or there is no history.
Plain strings and integers only, no import, so the Codon census compiles it.
"""

LANDINGS = "landings"
FLOOR_SOURCE = "floor"
# nemik:W1041: a round never holds fewer cards than this (when the ready set has them). The landed
# stacks undercount: mikemol-commit's records are the only landings read, so a repo that lands
# through another path, or one card to a stack, would otherwise get a round of one, the serial
# pattern the operator named (host 695f3e0a line 96999). A placeholder until capacity comes from
# what the host admits.
FLOOR = 3


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
        (the median size rounded up, never below FLOOR; where it came from: landings when the
        median alone is at least FLOOR, else floor, including when there is no history).

    """
    held = sorted(s for s in sizes if s > 0)
    if not held:
        return FLOOR, FLOOR_SOURCE
    middle = (len(held) + 1) // 2
    median = held[middle - 1]
    if median < FLOOR:
        return FLOOR, FLOOR_SOURCE
    return median, LANDINGS


SUPPLY = "supply"
# nemik:W1082: the most cards one gate run is taken to carry. Declared, not measured: the gate's
# cost per entry against the host's CPU headroom (drum's admission) is not read yet, so this
# stands for it. The round names it as the binding term when it binds, and says it is declared:
# a label that claims a measurement it does not have is the defect (github-8f, 2026-10-26, W1092).
CEILING = 6
CEILING_TERM = f"ceiling (declared {CEILING})"


def supply(manifests: list[list[str]], busy: list[str]) -> int:
    """Count the most ready cards that can stack without sharing a file.

    Args:
        manifests: Each ready card's planned files in rank order; an empty one is a card with no
            plan, which never stacks.
        busy: Files the cards being worked already hold.

    Returns:
        How many cards a greedy pick in rank order takes: each is disjoint from the files taken so
        far and from `busy`.

    """
    taken = set(busy)
    count = 0
    for files in manifests:
        if not files or taken.intersection(files):
            continue
        count += 1
        taken.update(files)
    return count


def width(stackable: int, landed: int, landed_source: str) -> tuple[int, str]:
    """Choose a round's width from what can stack, not only from what stacked before.

    The landed-stack median alone is circular: stacks are capped by the round that drew them, so
    it can never rise above where it started (github-8f, 2026-10-26).

    Args:
        stackable: What supply counted for the repo's ready cards.
        landed: The width capacity() gave from the landed stacks.
        landed_source: Where that came from.

    Returns:
        (the width, its binding term): the declared ceiling when the supply reaches CEILING,
        supply when it exceeds the landed width, else the landed width and its source.

    """
    if stackable >= CEILING:
        return max(CEILING, landed), CEILING_TERM
    if stackable > landed:
        return stackable, SUPPLY
    return landed, landed_source


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
