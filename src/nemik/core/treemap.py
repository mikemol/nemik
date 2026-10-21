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

    # fields declared at class level: Codon makes a class generic over its constructor's types
    # otherwise, and a bare `Tree` in an annotation then means Tree[NoneType, ...]
    parent: list[int]
    kids: list[list[int]]
    weight: list[int]
    own: list[int]
    roots: list[int]

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


def forest_of(parent: list[int], weight: list[int]) -> Tree:
    """Rebuild a forest from each card's parent and weight; a weight of 0 marks a closed card.

    The layout needs only these two, so a caller that holds them (the page, between the tree call
    and the layout call) need not send the edges again. Kids and roots come out in ascending order,
    as tree_of makes them; the own weights are not carried and read as 0.

    Args:
        parent: Each card's parent, NONE for a root or a closed card.
        weight: Each card's weight, 0 for a closed card.

    Returns:
        The forest.

    """
    n = len(parent)
    kids: list[list[int]] = [[] for _ in range(n)]
    roots: list[int] = []
    for card in range(n):
        if weight[card] == 0:
            continue
        if parent[card] == NONE:
            roots.append(card)
        else:
            kids[parent[card]].append(card)
    return Tree(parent, kids, weight, [0] * n, roots)


class Cells:
    """Where each card landed: a rectangle, its depth in the forest and its header height."""

    placed: list[bool]
    x: list[float]
    y: list[float]
    w: list[float]
    h: list[float]
    depth: list[int]
    head: list[float]

    def __init__(self, n: int) -> None:
        """Start with no card placed."""
        self.placed = [False] * n
        self.x = [0.0] * n
        self.y = [0.0] * n
        self.w = [0.0] * n
        self.h = [0.0] * n
        self.depth = [0] * n
        self.head = [0.0] * n


class _Layout:
    """The state of one ordered strip treemap: the forest, the ranking and the margins."""

    tree: Tree
    rank: dict[int, int]
    unranked: int
    pad: float
    head: float
    cells: Cells

    def __init__(self, tree: Tree, order: list[int], pad: float, head: float) -> None:
        """Rank the cards by their place in `order`; any card not in it sorts after all that are."""
        self.tree = tree
        self.rank = {card: i for i, card in enumerate(order)}
        self.unranked = len(order)
        self.pad = pad
        self.head = head
        self.cells = Cells(len(tree.parent))

    def _ordered(self, ids: list[int]) -> list[int]:
        """Put cards in rank order, the unranked last, ties to the lower index.

        Returns:
            The cards, first first.

        """
        pairs = sorted((self.rank.get(card, self.unranked), card) for card in ids)
        return [card for _, card in pairs]

    def _worst(self, strip: list[int], scale: float, width: float) -> float:
        """Give the worst aspect ratio among the tiles a strip would hold.

        Returns:
            The largest of w/h and h/w over the strip's tiles.

        """
        area = 0.0
        for card in strip:
            area += self.tree.weight[card] * scale
        height = area / width
        worst = 0.0
        for card in strip:
            tile = self.tree.weight[card] * scale / height
            worst = max(worst, tile / height, height / tile)
        return worst

    def _place(
        self, card: int, rect: tuple[float, float, float, float], depth: int
    ) -> None:
        """Set a card's cell, and lay its children inside it when it has any (a frame)."""
        x, y, w, h = rect
        cells = self.cells
        cells.placed[card] = True
        cells.x[card] = x
        cells.y[card] = y
        cells.w[card] = w
        cells.h[card] = h
        cells.depth[card] = depth
        cells.head[card] = 0.0
        if self.tree.kids[card]:
            # the header and margins shrink with a small cell, so children never leave it
            px = min(self.pad, w / 6)
            top = min(self.head, h / 3)
            py = min(self.pad, h / 6)
            cells.head[card] = top
            inner = (x + px, y + top, w - 2 * px, h - top - py)
            self.lay(self.tree.kids[card], inner, depth + 1)

    def lay(
        self, ids: list[int], rect: tuple[float, float, float, float], depth: int
    ) -> None:
        """Fill a rectangle with cards in horizontal strips.

        A strip closes when the next card would worsen its worst aspect ratio (Bederson et al.
        2002); area is proportional to weight.
        """
        rx, ry, rw, rh = rect
        if rw <= 0 or rh <= 0:
            for card in ids:
                self._place(card, (rx, ry, 0.0, 0.0), depth)
            return
        items = self._ordered(ids)
        total = 0
        for card in items:
            total += self.tree.weight[card]
        scale = (rw * rh) / total
        strips: list[list[int]] = []
        current: list[int] = []
        for card in items:
            if current and self._worst([*current, card], scale, rw) > self._worst(
                current, scale, rw
            ):
                strips.append(current)
                current = []
            current.append(card)
        if current:
            strips.append(current)
        y = ry
        for strip in strips:
            area = 0.0
            for card in strip:
                area += self.tree.weight[card] * scale
            height = area / rw
            x = rx
            for card in strip:
                width = self.tree.weight[card] * scale / height
                self._place(card, (x, y, width, height), depth)
                x += width
            y += height


def ordered_treemap(
    tree: Tree,
    order: list[int],
    rect: tuple[float, float, float, float],
    margins: tuple[float, float],
) -> Cells:
    """Lay the forest out as an ordered strip treemap (the page's orderedTreemap).

    Items in rank order fill horizontal strips, so order reads left to right, top to bottom, and
    area is proportional to weight. A card with work beneath it is a frame: it gets a header strip
    of its own and its children sit inside the margins.

    Args:
        tree: The forest from tree_of.
        order: The cards in rank order; a card not in it sorts after those that are.
        rect: (x, y, width, height) of the area to fill.
        margins: (pad, head): the margin and the header height at full size.

    Returns:
        Each open card's cell.

    """
    layout = _Layout(tree, order, margins[0], margins[1])
    layout.lay(tree.roots, rect, 0)
    return layout.cells
