# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""chains: the longest dependency chains of a graph of cards, over plain data (nemik:W818, W817).

The dependency order is a poset, so tied longest chains are alternatives, not a ranking
(nemik:W344). For every card this gives the height of the longest chain of prerequisites ending at
it (`up`), of dependents starting from it (`down`), and how many longest chains run through it. A
cycle is cut where the walk meets itself, so the answer depends on the order the cards are visited
in: the caller passes them in the order it wants them visited, and every adjacency list is walked
in that order.

The page's criticalSet (index.html) computes the same thing in JS; the two agree on the fixture
fleet (nemik:W817), and the page calls this once it is compiled to wasm.
"""


class Chains:
    """What `longest_chains` found."""

    def __init__(
        self,
        length: int,
        up: dict[str, int],
        down: dict[str, int],
        paths: dict[str, int],
    ) -> None:
        """Hold the longest chain's length, each card's heights and its chains through it."""
        self.length = length
        self.up = up
        self.down = down
        self.paths = paths


def _by(names: set[str] | list[str], key: dict[str, int]) -> list[str]:
    """Order names by their key, ties by name.

    Returns:
        The names, lowest key first.

    """
    pairs = sorted((key[n], n) for n in names)
    return [n for _, n in pairs]


def _heights(
    ids: list[str], rank: dict[str, int], edges: dict[str, set[str]]
) -> dict[str, int]:
    """Give the height of the longest chain starting at each card along `edges`.

    Returns:
        {card: height}, a lone card being 1.

    """
    memo: dict[str, int] = {}
    for start in ids:
        stack: list[tuple[str, list[str]]] = [(start, _by(edges[start], rank))]
        on_path = {start}
        while stack:
            node, todo = stack[-1]
            if node in memo:
                stack.pop()
                on_path.discard(node)
                continue
            while todo and (todo[-1] in memo or todo[-1] in on_path):
                todo.pop()
            if todo:
                nxt = todo.pop()
                on_path.add(nxt)
                stack.append((nxt, _by(edges[nxt], rank)))
                continue
            best = 0
            for e in edges[node]:
                if e in memo:
                    best = max(best, memo[e])
            memo[node] = 1 + best
            on_path.discard(node)
            stack.pop()
    return memo


def _ways(
    ids: list[str], back: dict[str, set[str]], height: dict[str, int]
) -> dict[str, int]:
    """Count, for each card, the longest chains that reach it from the end `height` measures.

    Args:
        ids: The cards.
        back: Each card's neighbours toward that end (its prerequisites for `up`).
        height: The heights toward that end.

    Returns:
        {card: ways}, 1 where the height is 1.

    """
    ways: dict[str, int] = {}
    for n in _by(ids, height):
        total = 0
        for p in back[n]:
            if height[p] == height[n] - 1:
                total += ways[p]
        ways[n] = 1 if height[n] == 1 else total
    return ways


def longest_chains(ids: list[str], deps: list[tuple[str, str]]) -> Chains:
    """Find the longest chains among `ids`.

    Args:
        ids: The cards, in the order to visit them (it settles how a cycle is cut).
        deps: (prerequisite, dependent) pairs; a pair naming a card not in `ids`, or a card with
            itself, is ignored.

    Returns:
        The length of the longest chain, each card's `up` and `down` heights, and for each card on a
        longest chain the number of longest chains through it.

    """
    rank = {n: i for i, n in enumerate(ids)}
    succ: dict[str, set[str]] = {n: set() for n in ids}
    pred: dict[str, set[str]] = {n: set() for n in ids}
    for x, y in deps:
        if x in rank and y in rank and x != y:
            succ[x].add(y)
            pred[y].add(x)
    down = _heights(ids, rank, succ)
    up = _heights(ids, rank, pred)
    length = 0
    for n in ids:
        length = max(length, up[n] + down[n] - 1)
    ways_in = _ways(ids, pred, up)
    ways_out = _ways(ids, succ, down)
    paths: dict[str, int] = {}
    for n in ids:
        if up[n] + down[n] - 1 == length:
            paths[n] = ways_in[n] * ways_out[n]
    return Chains(length, up, down, paths)
