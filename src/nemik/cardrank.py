# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W713: the downstream weight of a card over plain card edges, with no graph library.

nemik.rank.downstream_weight walks an rdflib graph. This is the same walk over `repo:W<n>` strings
so it can run where rdflib cannot (the browser port, nemik:W508): a card's successors as a mapping,
the done and blocked cards as sets, the three class weights as one tuple. The rdflib version stays
the reference; tests/test_cardrank.py checks the two agree on a fixture queue. The module imports
nothing, so the Codon census compiles it.
"""

Weights = tuple[int, int, int]  # (local, peer, peer_blocked)


def downstream_weight(
    succ: dict[str, list[str]],
    done: set[str],
    blocked: set[str],
    node: str,
    weights: Weights,
) -> int:
    """Sum the weights over the transitive downstream closure of a card, each counted once.

    A done card contributes nothing and is not traversed through: finished work waits on nothing.
    A cycle ends on the visited set, and the card itself never counts.

    Args:
        succ: card -> the cards it moves (what it enables, and every card that waits for it).
        done: The cards whose state is done.
        blocked: The cards whose state is blocked.
        node: The card whose downstream is weighed.
        weights: The weight of a card in the same repo, in another repo, and in another repo
            while blocked.

    Returns:
        The summed weight.

    """
    local, peer, peer_blocked = weights
    origin = node.partition(":")[0]
    seen = {node}
    stack = [node]
    total = 0
    while stack:
        for nxt in succ.get(stack.pop(), []):
            if nxt in seen or nxt in done:
                continue
            seen.add(nxt)
            stack.append(nxt)
            if nxt.partition(":")[0] == origin:
                total += local
            elif nxt in blocked:
                total += peer_blocked
            else:
                total += peer
    return total
