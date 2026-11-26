# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W976: the dependency cycles among open cards, over plain successor lists, no rdflib.

critical.cycles reads the rdflib graph. This is the same Tarjan over the successor map alone, so
the portable core (nemik:W422) can state its cycles without the graph: each is a strongly connected
component of more than one card, or a card that waits on itself. Iterative, so a long chain does
not meet the recursion limit; strings, lists and dicts only, so the Codon census compiles it.
tests/test_cardcritical.py holds it to critical.cycles on the same fixtures.
"""

FIRST_CHILD = 0
DONE = ""  # _advance's child when a card has no unvisited child left; a card name is never empty


def _advance(
    card: str,
    at: int,
    succ: dict[str, list[str]],
    marks: tuple[dict[str, int], dict[str, int], set[str]],
) -> tuple[int, str]:
    """Walk a card's children from the one at `at`, lowering its low link on the way.

    Args:
        card: The card being walked.
        at: The index of the next child to look at.
        succ: Each open card's open successors.
        marks: Tarjan's index and low-link numbers and the set of cards on the stack.

    Returns:
        (where to resume, the first child not yet visited), or (the end, DONE) when none is left.

    """
    index, low, on_stack = marks
    children = succ.get(card, [])
    while at < len(children):
        child = children[at]
        at += 1
        if child not in index:
            return at, child
        if child in on_stack:
            low[card] = min(low[card], index[child])
    return at, DONE


def _named(succ: dict[str, list[str]]) -> None:
    """Refuse an empty card name, which `_advance` would read as DONE.

    Raises:
        ValueError: when a card or a successor has an empty name: a card cite is never empty, so
            that is a defect in the caller, never a card to read past.

    """
    for card, children in succ.items():
        if card == DONE or DONE in children:
            msg = "a card with an empty name"
            raise ValueError(msg)


def _pop_group(stack: list[str], on_stack: set[str], root: str) -> list[str]:
    """Pop the cards of one strongly connected component off Tarjan's stack, down to its root.

    Returns:
        The component's cards, last pushed first.

    """
    group: list[str] = []
    while True:
        member = stack.pop()
        on_stack.discard(member)
        group.append(member)
        if member == root:
            return group


def cycles_of(
    succ: dict[str, list[str]], human: set[str]
) -> list[tuple[list[str], bool]]:
    """Find the dependency cycles among open cards.

    Args:
        succ: Each open card's open successors (what it enables and what waits for it), sorted;
            a card absent as a key has none.
        human: The cards blocked on the operator.

    Returns:
        Each cycle as (its sorted cards, operator breakable), sorted. Breakable means a member is
        in `human`: two repos' asks may cite each other on purpose and the operator's answer
        ends it; any other cycle is a true deadlock.

    An empty card name is refused with a ValueError, raised by a callee (see `_named`).

    """
    _named(succ)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    found: list[tuple[list[str], bool]] = []
    for root in sorted(succ):
        if root in index:
            continue
        work: list[tuple[str, int]] = [(root, FIRST_CHILD)]
        while work:
            card, at = work.pop()
            if card not in index:
                index[card] = len(index)
                low[card] = index[card]
                stack.append(card)
                on_stack.add(card)
            at, child = _advance(card, at, succ, (index, low, on_stack))
            if child != DONE:
                work.extend([(card, at), (child, FIRST_CHILD)])
                continue
            if low[card] == index[card]:
                group = _pop_group(stack, on_stack, card)
                if len(group) > 1 or card in succ.get(card, []):
                    found.append((sorted(group), any(m in human for m in group)))
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[card])
    return sorted(found)
