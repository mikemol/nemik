# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""treemap: the enables forest and its ordered treemap, over plain data (nemik:W826, W827, W816).

The page lays its cards out as a treemap (nemik:W180, the operator's "reminiscent of a treemap").
The model is pure: this is its Python, which the CLI tools and the page share (compiled by Codon
to wasm, goal W812); the page's JS copy is retired when the module replaces it.

Cards are numbered 0 to n-1 in ascending id order, which the caller arranges: the original breaks
every tie by comparing ids as strings, and index order is that order. An edge is
(source, target, kind) with kind 0 for enables and 1 for waits; -1 stands for "no card".
"""

ENABLES = 0
WAITS = 1
NONE = -1


class Tree:
    """The enables forest of the open cards: one parent each, and what each carries."""

    def __init__(
        self,
        parent: list[int],
        kids: list[list[int]],
        weight: list[int],
        own: list[int],
        roots: list[int],
    ) -> None:
        """Hold the parent of each card, its children, its weights and the roots.

        A root or a closed card has the parent NONE; a card's weight is its own plus its
        children's; the roots are in ascending order.
        """
        self.parent = parent
        self.kids = kids
        self.weight = weight
        self.own = own
        self.roots = roots


def _depth_up(card: int, ups: list[list[int]], reach: dict[int, int]) -> int:
    """Count how many open things a card sits under, transitively; a cycle is cut where it closes.

    Returns:
        The longest chain of enables above the card.

    """
    if card in reach:
        return reach[card]
    reach[card] = 0
    deepest = 0
    for up in ups[card]:
        deepest = max(deepest, 1 + _depth_up(up, ups, reach))
    reach[card] = deepest
    return deepest


def _cut_cycles(opened: list[int], parent: list[int]) -> None:
    """Make a root of the lowest card of every cycle among the chosen parents."""
    for card in opened:
        seen: set[int] = set()
        at = card
        while at != NONE and at not in seen:
            seen.add(at)
            at = parent[at]
        if at != NONE:
            ring = [at]
            nxt = parent[at]
            while nxt != at:
                ring.append(nxt)
                nxt = parent[nxt]
            parent[min(ring)] = NONE


def _owns(opened: list[int], succ: list[list[int]], n: int) -> list[int]:
    """Count, for each open card, itself and every open card it moves downstream.

    Returns:
        The count per card (0 for a card that is not open).

    """
    own = [0] * n
    for card in opened:
        seen = {card}
        todo = [card]
        while todo:
            for down in succ[todo.pop()]:
                if down not in seen:
                    seen.add(down)
                    todo.append(down)
        own[card] = len(seen)
    return own


def _weigh(card: int, kids: list[list[int]], own: list[int], weight: list[int]) -> int:
    """Give a card's weight: its own plus its children's, memoised in `weight`.

    Returns:
        The weight.

    """
    if weight[card] != 0:
        return weight[card]
    total = own[card]
    for kid in kids[card]:
        total += _weigh(kid, kids, own, weight)
    weight[card] = total
    return total


def tree_of(n: int, is_open: list[bool], edges: list[tuple[int, int, int]]) -> Tree:
    """Build the enables forest of the open cards (the page's treeOf).

    Each open card's parent is the heaviest open thing it enables: the one with the longest chain
    above it, ties to the lower index. A second parent stays a drawn edge. A card's weight is its
    own (1 plus the open cards it moves downstream, over enables and waits alike, so a load-bearing
    leaf is a big tile) plus the weight of everything beneath it in the forest.

    Args:
        n: How many cards there are.
        is_open: Per card, whether it is open (not done, not dropped).
        edges: (source, target, kind) triples.

    Returns:
        The forest.

    """
    opened = [i for i in range(n) if is_open[i]]
    ups: list[list[int]] = [[] for _ in range(n)]
    succ: list[list[int]] = [[] for _ in range(n)]
    for source, target, kind in edges:
        if not (is_open[source] and is_open[target]) or source == target:
            continue
        if kind == ENABLES:
            ups[source].append(target)
        upstream, downstream = (target, source) if kind == WAITS else (source, target)
        succ[upstream].append(downstream)
    reach: dict[int, int] = {}
    parent = [NONE] * n
    for card in opened:
        best = NONE
        best_depth = -1
        for cand in ups[card]:
            depth = _depth_up(cand, ups, reach)
            if depth > best_depth or (depth == best_depth and cand < best):
                best = cand
                best_depth = depth
        parent[card] = best
    _cut_cycles(opened, parent)
    kids: list[list[int]] = [[] for _ in range(n)]
    for card in opened:
        if parent[card] != NONE:
            kids[parent[card]].append(card)
    own = _owns(opened, succ, n)
    weight = [0] * n
    for card in opened:
        _weigh(card, kids, own, weight)
    roots = [card for card in opened if parent[card] == NONE]
    return Tree(parent, kids, weight, own, roots)
