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

from rdflib import Graph
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM
from nemik.blocks import ref
from nemik.rank import successors


class Critical(NamedTuple):
    length: int
    chain: list[str]
    slack: dict[str, int]


def critical(g: Graph) -> Critical:
    """The critical path of the open graph: its length, its zero-slack cards in dependency order,
    and every open card's slack."""
    nodes = {
        n
        for n in g.subjects(OSLC_CM.state, None)
        if (n, OSLC_CM.state, NEMIK.Done) not in g
    }
    succ = {n: {s for s in successors(g, n) if s in nodes and s != n} for n in nodes}
    pred: dict[Node, set[Node]] = {n: set() for n in nodes}
    for n, outs in succ.items():
        for s in outs:
            pred[s].add(n)

    def longest(edges: dict[Node, set[Node]]) -> dict[Node, int]:
        memo: dict[Node, int] = {}
        for start in sorted(nodes, key=str):
            stack: list[tuple[Node, list[Node]]] = [
                (start, sorted(edges[start], key=str))
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
                    stack.append((nxt, sorted(edges[nxt], key=str)))
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
    slack = {ref(n): length - through[n] for n in nodes}
    # ONE longest chain: from a card that starts a longest path, step to the dependent that keeps it
    # longest. (Ties give several equal chains; the zero-slack count says how many cards are on any.)
    starts = sorted((n for n in nodes if through[n] == length and up[n] == 1), key=str)
    chain: list[Node] = []
    here = starts[0] if starts else None
    while here is not None:
        chain.append(here)
        here = next(
            (
                s
                for s in sorted(succ[here], key=str)
                if through[s] == length and down[s] == down[here] - 1
            ),
            None,
        )
    return Critical(length, [ref(n) for n in chain], slack)


def main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """nemik-critical: the longest chain of open work across the fleet, and what has slack."""
    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(
        prog="nemik-critical", description=(main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    found = critical(g)
    if args.json:
        print(json.dumps(found._asdict(), indent=1))
        return
    print(f"critical path: {found.length} open cards deep")
    print("  " + " -> ".join(found.chain))
    loose = sum(1 for s in found.slack.values() if s > 0)
    print(f"  {len(found.slack) - loose} cards at zero slack, {loose} with slack")
