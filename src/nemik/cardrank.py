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
WEIGHT_KEYS = ("local", "peer", "peer_blocked", "operator")


def parse_weights(text: str) -> tuple[int, int, int, int]:
    """Read the edge weights from the weights file's text, with no TOML library (nemik:W868).

    The weights are the file's top-level integers, before its first `[table]`: `local`, `peer` and
    `peer_blocked`, and `operator`, which a text that does not name it leaves at zero. Everything
    after the first table header is another table's and is ignored. It reads what
    rank.load_weights reads, and like it a missing required weight is a KeyError; the tests hold
    the two equal on the packaged file.

    Args:
        text: The weights file's text.

    Returns:
        (local, peer, peer_blocked, operator).

    """
    found: dict[str, int] = {}
    for raw in text.splitlines():
        line = raw.partition("#")[0].strip()
        if line.startswith("["):
            break
        key, equals, value = line.partition("=")
        if equals and key.strip() in WEIGHT_KEYS:
            found[key.strip()] = int(value.strip())
    return (
        found["local"],
        found["peer"],
        found["peer_blocked"],
        found.get("operator", 0),
    )


def cone(needs: dict[str, list[str]], front: set[str], source: str) -> list[str]:
    """Collect a card and everything it transitively needs, over plain edges (nemik:W870).

    The same selection as nemik.flow's cone. A ready card is on the frontier and has no
    prerequisites to follow, so the walk stops there; a cycle ends on the visited set.

    Args:
        needs: card -> the cards it waits on.
        front: The ready cards, the ground of the flow model.
        source: The card whose prerequisite closure is wanted.

    Returns:
        The cards, sorted.

    """
    seen: set[str] = set()
    stack = [source]
    while stack:
        card = stack.pop()
        if card in seen:
            continue
        seen.add(card)
        if card not in front:
            stack.extend(needs.get(card, []))
    return sorted(seen)


def unknowns(nodes: list[str], front: set[str]) -> list[str]:
    """Pick the cards a flow solve must find a potential for: everything but the ground.

    Args:
        nodes: A cone's cards.
        front: The ready cards, held at potential zero.

    Returns:
        The cards not on the frontier, in the order given.

    """
    return [node for node in nodes if node not in front]


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
