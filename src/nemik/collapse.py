# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W692: blocked cards rolled up into umbrellas under the node that dominates them.

The operator (2026-10-18, session 695f3e0a lines 80452, 80496, 80516 and 80535) looked at a row of
sibling blocked cards in the graph and ruled that blocked cards blocked by the same card collapse
into one umbrella A_C_u; that the umbrella is an emergent, virtual card (a graph on screen, an
n-path in CLI tooling); that the rule applies recursively, a deep tree of blocked nodes clumping
into higher and higher umbrellas; that the blocked_on edges form a DAG and a card cannot roll up
into a node it is blocked on more than; that a card cannot roll up into a node if it enables nodes
that are not transitively blocked behind that target; and that if A depends on B1 and B2 and both
depend only on C, A rolls up to C transitively.

One structure covers all of that, as github-8f read it: X rolls up under T exactly when every
blocked_on path from X reaches T, that is, T dominates X in the blocked_on graph. The dominator tree
is computed once (Cooper, Harvey and Kennedy's iterative algorithm); a node's umbrella is the set of
blocked nodes whose immediate dominator it is, when there are two or more; an n-path is the chain of
umbrellas along the dominator chain, and the recursion is the tree itself. The enables rule is the
integrity check: a card whose enables names a card that T does not dominate is a data-integrity
finding (`violations`, for nemik-check to warn on) and is left out of the umbrella.

This is the grouping over plain data, so nemik-check and serve.py read one answer. Nothing is
written to a queue; members keep their own symbols. The module imports nothing, so the Codon census
compiles it.
"""

Row = tuple[list[str], list[str]]
Umbrella = tuple[str, list[str], list[str], list[str]]
Violation = tuple[str, str, str]
ENTRY = "\x00entry"
MIN_MEMBERS = 2


def reverse_graph(blocked: dict[str, Row]) -> dict[str, list[str]]:
    """Build the graph the dominators are taken over: from what blocks, to what it blocks.

    Args:
        blocked: For each blocked card, the cards it waits on and the cards it enables.

    Returns:
        node -> the nodes it blocks. A virtual entry points at every node that waits on nothing
        (an unblocked card, or a blocker that is not itself a blocked card).

    """
    nodes: set[str] = set(blocked)
    for waits, enables in blocked.values():
        nodes.update(waits)
        nodes.update(enables)
    succ: dict[str, list[str]] = {n: [] for n in nodes}
    succ[ENTRY] = []
    for node in sorted(nodes):
        waits = sorted(set(blocked[node][0])) if node in blocked else []
        if not waits:
            succ[ENTRY].append(node)
        for blocker in waits:
            succ[blocker].append(node)
    return succ


def postorder(succ: dict[str, list[str]]) -> list[str]:
    """Order the nodes reachable from the entry, children before parents.

    Args:
        succ: The graph.

    Returns:
        A depth-first postorder from the entry, computed without recursion.

    """
    seen: set[str] = set()
    out: list[str] = []
    stack: list[tuple[str, int]] = [(ENTRY, 0)]
    while stack:
        node, i = stack.pop()
        if i == 0:
            if node in seen:
                continue
            seen.add(node)
        kids = succ.get(node, [])
        if i < len(kids):
            stack.append((node, i + 1))
            if kids[i] not in seen:
                stack.append((kids[i], 0))
        else:
            out.append(node)
    return out


def meet(a: str, b: str, idom: dict[str, str], rank: dict[str, int]) -> str:
    """Find the nearest common dominator of two nodes.

    Args:
        a: One node.
        b: Another.
        idom: The immediate dominators found so far.
        rank: Each node's place in the postorder.

    Returns:
        The node where their dominator chains meet.

    """
    while a != b:
        while rank[a] < rank[b]:
            a = idom[a]
        while rank[b] < rank[a]:
            b = idom[b]
    return a


def immediate_dominators(blocked: dict[str, Row]) -> dict[str, str]:
    """Compute each node's immediate dominator in the blocked_on graph.

    Args:
        blocked: For each blocked card, the cards it waits on and the cards it enables.

    Returns:
        node -> the nearest node that every blocked_on path from it must reach; the virtual entry
        for a node with no single such blocker. A node on a blocked_on cycle with no way out is
        absent.

    """
    succ = reverse_graph(blocked)
    post = postorder(succ)
    rank = {n: k for k, n in enumerate(post)}
    preds: dict[str, list[str]] = {n: [] for n in post}
    for node in post:
        for child in succ[node]:
            if child in preds:
                preds[child].append(node)
    idom = {ENTRY: ENTRY}
    changed = True
    while changed:
        changed = False
        for node in reversed(post):
            if node == ENTRY:
                continue
            new = ""
            for pred in preds[node]:
                if pred in idom:
                    new = pred if not new else meet(pred, new, idom, rank)
            if new and idom.get(node) != new:
                idom[node] = new
                changed = True
    return idom


def dominated_by(idom: dict[str, str], node: str, target: str) -> bool:
    """Say whether a target dominates a node.

    Args:
        idom: What `immediate_dominators` returned.
        node: The node.
        target: The candidate dominator.

    Returns:
        True when the target is on the node's dominator chain; a node outside the graph is not
        dominated by anything.

    """
    while node in idom and node != ENTRY:
        node = idom[node]
        if node == target:
            return True
    return False


def violations(blocked: dict[str, Row]) -> list[Violation]:
    """Find the enables edges that leave the subtree of the card's dominator.

    Args:
        blocked: For each blocked card, the cards it waits on and the cards it enables.

    Returns:
        (card, target, escaped) for each blocked card that has a dominator T other than the entry
        and enables a card that T does not dominate: the enables and blocked_on edges disagree.
        Sorted.

    """
    idom = immediate_dominators(blocked)
    out: list[Violation] = []
    for card, (_, enables) in blocked.items():
        target = idom.get(card, ENTRY)
        if target != ENTRY:
            out.extend(
                (card, target, e)
                for e in sorted(set(enables))
                if not dominated_by(idom, e, target)
            )
    return sorted(out)


def collapse(blocked: dict[str, Row]) -> list[Umbrella]:
    """Roll the blocked cards up into umbrellas by their immediate dominators.

    Args:
        blocked: For each blocked card (any id: `W<n>` or `repo:W<n>`), the cards it waits on and
            the cards it enables, each as a list.

    Returns:
        (id, blockers, enables, members) for every node that immediately dominates two or more
        blocked cards that keep their enables inside its subtree, sorted by id; blockers is that
        node and enables the members' enables.

    """
    idom = immediate_dominators(blocked)
    held: dict[str, list[str]] = {}
    for card in sorted(blocked):
        target = idom.get(card, ENTRY)
        stays = all(dominated_by(idom, e, target) for e in blocked[card][1])
        if target != ENTRY and stays:
            held.setdefault(target, []).append(card)
    out: list[Umbrella] = []
    for target, members in held.items():
        if len(members) >= MIN_MEMBERS:
            enables = sorted({e for m in members for e in blocked[m][1]})
            out.append((umbrella_id(target, members), [target], enables, members))
    return sorted(out)


def umbrella_id(target: str, members: list[str]) -> str:
    """Name an umbrella A_C_u: its first member, the node it sits under, and u.

    Args:
        target: The node that dominates the members (C).
        members: The collapsed nodes (A), sorted.

    Returns:
        The id, for example `W518_W517_u`.

    """
    return f"{members[0]}_{target}_u"


def paths(blocked: dict[str, Row], umbrellas: list[Umbrella]) -> dict[str, str]:
    """Give each collapsed card its n-path address: the umbrellas along its dominator chain.

    Args:
        blocked: What `collapse` was given.
        umbrellas: What `collapse` returned.

    Returns:
        card -> `outer/inner/.../card` for every member of an umbrella, the umbrellas ordered from
        the one nearest the roots down to the card's own, the card last.

    """
    idom = immediate_dominators(blocked)
    named = {target[0]: name for name, target, _, _ in umbrellas}
    out: dict[str, str] = {}
    for _, _, _, members in umbrellas:
        for card in members:
            chain: list[str] = []
            node = idom[card]
            while node != ENTRY:
                if node in named:
                    chain.insert(0, named[node])
                node = idom[node]
            out[card] = "/".join([*chain, card])
    return out


def label(blockers: list[str], enables: list[str], members: list[str]) -> str:
    """Say what an umbrella holds, for its node and the nemik-check Info.

    Args:
        blockers: The node that dominates the members (C).
        enables: The cards the members enable (B).
        members: The collapsed nodes (A).

    Returns:
        A short line: the member count, what they wait on, what they enable.

    """
    waits = ", ".join(blockers) if blockers else "nothing"
    opens = ", ".join(enables) if enables else "nothing"
    return f"{len(members)} cards collapse under {waits} (they enable {opens})"
