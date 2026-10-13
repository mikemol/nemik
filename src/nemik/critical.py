"""nemik:W313: the critical path through the open dependency graph, and each card's slack.

Every open card counts one step. `up` is the length of the longest chain of open prerequisites ending at
the card, `down` the longest chain of open dependents starting at it; the longest path through the whole
graph is the critical path (length L), and a card's slack is L minus the longest path through that card:
how far it can slip before it lengthens the whole. A zero-slack card is on a longest chain. A cycle is
cut where the walk meets itself, as the rest of nemik does.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NamedTuple

from rdflib import Graph, Literal
from rdflib.term import Node

from nemik.adapter import BASE, NEMIK, OSLC_CM
from nemik.blocks import ref
from nemik.cards import Card
from nemik.rank import successors


class Critical(NamedTuple):
    length: int
    chain: list[
        str
    ]  # every card on some longest chain, by (rank, cite): a display order, not a ranking
    slack: dict[str, int]
    rank: dict[
        str, int
    ]  # the height of each open card: the longest chain of prerequisites ending at it
    paths: dict[
        str, int
    ]  # longest chains through each critical card (ways in x ways out)


def _open(g: Graph) -> set[Node]:
    from nemik.index import index

    ix = index(g)
    if ix is not None:
        return {n for n in ix.state if ix.open(n)}
    return {
        n
        for n in g.subjects(OSLC_CM.state, None)
        if (n, OSLC_CM.state, NEMIK.Done) not in g
    }


def repo_scope(g: Graph, repo: str) -> set[str]:
    """nemik:W333: the open cards of one repo, as cites: the scope of that repo's own critical path."""
    return {c for c in (ref(n) for n in _open(g)) if c.partition(":")[0] == repo}


def cone(g: Graph, card: str) -> set[str]:
    """nemik:W333: `card` with everything it transitively waits on and everything transitively
    waiting on it (open cards only): the scope of the selected card's longest chain."""
    nodes = _open(g)
    start = next((n for n in nodes if ref(n) == card), None)
    if start is None:
        return set()
    succ = {n: {s for s in successors(g, n) if s in nodes} for n in nodes}
    pred: dict[Node, set[Node]] = {n: set() for n in nodes}
    for n, outs in succ.items():
        for s in outs:
            pred[s].add(n)
    seen = {start}
    for edges in (succ, pred):
        todo = [start]
        while todo:
            for nxt in edges[todo.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
    return {ref(n) for n in seen}


def critical(g: Graph, scope: set[str] | None = None) -> Critical:
    """The critical path of the open graph: its length, its zero-slack cards in dependency order,
    and every open card's slack. With `scope` (a set of cites, W333) only those cards count, so the
    path and slack are the longest within a repo, a visible set, or one card's cone."""
    from nemik.cards import cards

    return critical_cards(cards(g), scope)


def _key(cite: str) -> str:
    # the order the graph version visited cards in (their URIs), so cycle-breaking, which depends on
    # visiting order, gives the same answer: "a:W1" and "a0:W1" sort differently as cites than as URIs
    return BASE + cite.replace(":", "/", 1)


def critical_cards(by_cite: dict[str, Card], scope: set[str] | None = None) -> Critical:
    """nemik:W453: `critical` over plain `Card`s, no rdflib: the portable core (W422, W425).

    A card's successors are what it enables and what waits for it, so `y` follows `x` when `x` is in
    `y.enabled_by` or `y.waits_for`. Open means not done, as the graph version counted it.
    """
    nodes = {c for c, card in by_cite.items() if not card.done}
    if scope is not None:
        nodes = {c for c in nodes if c in scope}
    succ: dict[str, set[str]] = {n: set() for n in nodes}
    for y in nodes:
        card = by_cite[y]
        for x in (*card.enabled_by, *card.waits_for):
            if x in nodes and x != y:
                succ[x].add(y)
    pred: dict[str, set[str]] = {n: set() for n in nodes}
    for n, outs in succ.items():
        for s in outs:
            pred[s].add(n)

    def longest(edges: dict[str, set[str]]) -> dict[str, int]:
        memo: dict[str, int] = {}
        for start in sorted(nodes, key=_key):
            stack: list[tuple[str, list[str]]] = [
                (start, sorted(edges[start], key=_key))
            ]
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
                    stack.append((nxt, sorted(edges[nxt], key=_key)))
                    continue
                memo[node] = 1 + max(
                    (memo[e] for e in edges[node] if e in memo), default=0
                )
                on_path.discard(node)
                stack.pop()
        return memo

    down, up = longest(succ), longest(pred)
    through = {n: up[n] + down[n] - 1 for n in nodes}
    length = max(through.values(), default=0)
    slack = {n: length - through[n] for n in nodes}
    # nemik:W344: the dependency order is a poset, so tied longest chains are alternatives, not a ranking:
    # the critical object is EVERY card on some longest chain (zero slack), graded by its rank (`up`), and
    # by how many longest chains run through it (ways in x ways out). Nothing here depends on sort order
    # except the order the list is displayed in: (rank, cite).
    ways_in: dict[str, int] = {}
    for n in sorted(nodes, key=lambda x: up[x]):
        ways_in[n] = (
            1 if up[n] == 1 else sum(ways_in[p] for p in pred[n] if up[p] == up[n] - 1)
        )
    ways_out: dict[str, int] = {}
    for n in sorted(nodes, key=lambda x: down[x]):
        ways_out[n] = (
            1
            if down[n] == 1
            else sum(ways_out[s] for s in succ[n] if down[s] == down[n] - 1)
        )
    on_longest = [n for n in nodes if through[n] == length]
    chain = sorted(on_longest, key=lambda n: (up[n], _key(n)))
    return Critical(
        length,
        chain,
        slack,
        {n: up[n] for n in nodes},
        {n: ways_in[n] * ways_out[n] for n in on_longest},
    )


def cycles(g: Graph) -> list[tuple[list[str], bool]]:
    """nemik:W324: the dependency cycles among open cards, each as (its sorted cards, operator
    breakable): a strongly connected component of more than one card, or a card that waits on itself.
    Every card in one waits on another, so it cannot clear by itself. It IS breakable when a member is
    blocked on the operator (blocked_kind human): the `same ask as` convention makes two repos' asks
    cite each other on purpose, and the operator's answer ends it. Any other cycle is a true
    deadlock. Tarjan's algorithm; depth is bounded by a simple path."""
    nodes = {
        n
        for n in g.subjects(OSLC_CM.state, None)
        if (n, OSLC_CM.state, NEMIK.Done) not in g
    }
    succ = {
        n: sorted((s for s in successors(g, n) if s in nodes), key=str) for n in nodes
    }
    index: dict[Node, int] = {}
    low: dict[Node, int] = {}
    on_stack: set[Node] = set()
    stack: list[Node] = []
    found: list[tuple[list[str], bool]] = []

    def visit(v: Node) -> None:
        index[v] = low[v] = len(index)
        stack.append(v)
        on_stack.add(v)
        for w in succ[v]:
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            group = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                group.append(w)
                if w == v:
                    break
            if len(group) > 1 or v in succ[v]:
                human = any(
                    (n, NEMIK.blockedKind, Literal("human")) in g for n in group
                )
                found.append((sorted(ref(n) for n in group), human))

    for n in sorted(nodes, key=str):
        if n not in index:
            visit(n)
    return sorted(found)


def assume_done(g: Graph, cites: list[str]) -> Graph:
    """nemik:W351: a copy of `g` in which each named card (`repo:W<n>`) is closed. `g` is untouched."""
    out = Graph()
    out += g
    wanted = set(cites)
    for node in list(out.subjects(OSLC_CM.state, None)):
        if ref(node) in wanted:
            out.remove((node, OSLC_CM.state, None))
            out.add((node, OSLC_CM.state, NEMIK.Done))
    return out


class Fire(NamedTuple):
    cite: str
    planned: list[str]  # open forecast (tick-minted) cards downstream of it
    delay: int  # how many cards longer the scope's critical path is because it is open


def fires(g: Graph, scope: set[str] | None = None) -> list[Fire]:
    """nemik:W347: fire ripple. Each open card minted during an interrupt, with the planned work it
    holds up: the open tick-minted cards downstream of it, and how much longer the scope's critical
    path is while it stays open (its length now, minus the length if it were done). Only fires that
    hold up planned work are listed, heaviest delay first."""
    nodes = _open(g)
    if scope is not None:
        nodes = {n for n in nodes if ref(n) in scope}
    succ = {n: {s for s in successors(g, n) if s in nodes} for n in nodes}

    def minted(n: Node) -> str:
        return str(g.value(n, NEMIK.mintedDuring) or "")

    base = critical(g, scope).length
    out: list[Fire] = []
    for n in sorted(nodes, key=str):
        if minted(n) != "interrupt":
            continue
        seen, todo = {n}, [n]
        while todo:
            for nxt in succ[todo.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        planned = sorted(ref(x) for x in seen - {n} if minted(x) == "tick")
        if not planned:
            continue
        delay = base - critical(assume_done(g, [ref(n)]), scope).length
        out.append(Fire(ref(n), planned, delay))
    return sorted(out, key=lambda f: (-f.delay, -len(f.planned), f.cite))


def what_if(before: Critical, after: Critical, cites: list[str]) -> str:
    """The delta a what-if makes: path length, the cards that leave or join a longest chain, and the
    open cards whose slack changed (the closed ones themselves are not counted)."""
    left = sorted(set(before.chain) - set(after.chain) - set(cites))
    joined = sorted(set(after.chain) - set(before.chain))
    moved = sorted(
        c
        for c in after.slack
        if c in before.slack and after.slack[c] != before.slack[c]
    )
    lines = [
        f"assume done: {', '.join(cites)}",
        f"  critical path: {before.length} -> {after.length} open cards deep",
        f"  leave a longest chain: {', '.join(left) or 'none'}",
        f"  join a longest chain: {', '.join(joined) or 'none'}",
        f"  slack changed on {len(moved)} open card(s)",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """nemik-critical: the longest chain of open work across the fleet, and what has slack."""
    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(
        prog="nemik-critical", description=(main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--repo", help="the longest chain within this repo only (W333)")
    ap.add_argument(
        "--card", help="the longest chain through this card's cone, <repo>:W<n>"
    )
    ap.add_argument(
        "--assume-done",
        nargs="+",
        metavar="REPO:W<n>",
        default=[],
        help="what-if: the path and slack as if these cards were closed, against today's (W351)",
    )
    ap.add_argument(
        "--fires",
        action="store_true",
        help="each open interrupt card that holds up planned (tick-minted) work, and how much "
        "longer the critical path is while it stays open (W347)",
    )
    args = ap.parse_args(argv)
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    scope: set[str] | None = None
    if args.repo:
        scope = repo_scope(g, args.repo)
    if args.card:
        around = cone(g, args.card)
        scope = around if scope is None else scope & around
    if args.fires:
        found_fires = fires(g, scope)
        if args.json:
            print(json.dumps([f._asdict() for f in found_fires], indent=1))
            return
        print(f"fires holding up planned work: {len(found_fires)}")
        for f in found_fires:
            print(
                f"  {f.cite}  delays the path {f.delay}, holds up {len(f.planned)} planned: "
                + ", ".join(f.planned[:8])
                + (" ..." if len(f.planned) > 8 else "")
            )
        return
    if args.assume_done:
        # nemik:W351: what-if. The same scope, on a copy where the named cards are closed.
        before = critical(g, scope)
        g = assume_done(g, args.assume_done)
        after = critical(g, scope)
        if args.json:
            print(json.dumps({"before": before._asdict(), "after": after._asdict()}))
            return
        print(what_if(before, after, args.assume_done))
        return
    found = critical(g, scope)
    loops = cycles(g)
    if args.json:
        print(json.dumps({**found._asdict(), "cycles": loops}, indent=1))
        return
    print(f"critical path: {found.length} open cards deep")
    # nemik:W344: one line per rank; cards sharing a rank are tied alternatives (an antichain), joined by |
    levels: dict[int, list[str]] = {}
    for card in found.chain:
        levels.setdefault(found.rank[card], []).append(card)
    print(
        "  "
        + " -> ".join(
            "|".join(cards) + (f" (x{len(cards)} tied)" if len(cards) > 1 else "")
            for _, cards in sorted(levels.items())
        )
    )
    loose = sum(1 for s in found.slack.values() if s > 0)
    print(f"  {len(found.slack) - loose} cards at zero slack, {loose} with slack")
    # nemik:W324: a cycle never clears; a cross-repo one spans workstreams that cannot see it alone.
    deadlocks = [c for c, human in loops if not human]
    print(
        f"dependency cycles: {len(loops)}, "
        f"{len(deadlocks)} true deadlocks, {len(loops) - len(deadlocks)} the operator can break"
    )
    for cards, human in loops:
        repos = {c.partition(":")[0] for c in cards}
        mark = " [cross-repo]" if len(repos) > 1 else ""
        kind = "operator can break" if human else "DEADLOCK"
        print(f"  {kind}: {', '.join(cards)}{mark}")
