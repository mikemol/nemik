# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W713: the downstream weight of a card over plain card edges, with no graph library.

nemik.rank.downstream_weight walks an rdflib graph. This is the same walk over `repo:W<n>` strings
so it can run where rdflib cannot (the browser port, nemik:W508): a card's successors as a mapping,
the done and blocked cards as sets, the three class weights as one tuple. The rdflib version stays
the reference; tests/test_cardrank.py checks the two agree on a fixture queue. The module imports
nothing but heapq, so the Codon census compiles it.
"""

import heapq

Weights = tuple[int, int, int]  # (local, peer, peer_blocked)
WEIGHT_KEYS = ("local", "peer", "peer_blocked", "operator")
# one elimination: the node, its pivot and its neighbours with their couplings
Steps = list[tuple[str, float, dict[str, float]]]


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


def _laplacian(
    edges: list[tuple[str, str, float]], front: set[str], nodes: list[str]
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Build the grounded Laplacian of a cone: each unknown's diagonal and its couplings.

    Args:
        edges: (card, prerequisite, conductance) for each dependency inside the cone.
        front: The ready cards, which are the ground and have no row.
        nodes: The cone's cards.

    Returns:
        (the diagonal per unknown node, its couplings to the other unknown nodes).

    """
    diag: dict[str, float] = {}
    link: dict[str, dict[str, float]] = {}
    for node in nodes:
        if node not in front:
            diag[node] = 0.0
            link[node] = {}
    for u, v, w in edges:
        for a, b in ((u, v), (v, u)):
            if a in diag:
                diag[a] += w
                if b in diag:
                    link[a][b] = link[a].get(b, 0.0) + w
    return diag, link


def _eliminate(
    diag: dict[str, float], link: dict[str, dict[str, float]], rhs: dict[str, float]
) -> Steps:
    """Eliminate the unknown nodes one at a time, lowest degree first and ties by name.

    The node of the least degree is found with a heap of (degree, name) whose stale entries are
    skipped, the order flow.py's heap gives. Each node's pivot and neighbours are kept for the back
    substitution.

    Args:
        diag: The diagonal per unknown node; updated in place.
        link: The couplings among the unknown nodes; consumed.
        rhs: The injected demand per unknown node; updated in place.

    Returns:
        The eliminations in order.

    Raises:
        ZeroDivisionError: A component has no ground (the pivot of its last node is zero).

    """
    steps: Steps = []
    heap: list[tuple[int, str]] = []
    for node, neighbours in link.items():
        heap.append((len(neighbours), node))
    heapq.heapify(heap)
    while link:
        degree, k = heapq.heappop(heap)
        if k not in link or len(link[k]) != degree:
            continue
        pivot = diag[k]
        if not pivot:
            msg = "a component with no ground"
            raise ZeroDivisionError(msg)
        around = link.pop(k)
        for i in sorted(around):
            g_i = around[i]
            diag[i] -= g_i * g_i / pivot
            rhs[i] += g_i / pivot * rhs[k]
            del link[i][k]
            for j in around:
                if j != i:
                    link[i][j] = link[i].get(j, 0.0) + g_i * around[j] / pivot
            heapq.heappush(heap, (len(link[i]), i))
        steps.append((k, pivot, around))
    return steps


def _substitute(steps: Steps, rhs: dict[str, float]) -> dict[str, float]:
    """Back-substitute the eliminations, last first, into a potential per unknown node.

    Args:
        steps: What _eliminate returned.
        rhs: The right-hand side after elimination.

    Returns:
        The potential at each unknown node.

    """
    potential: dict[str, float] = {}
    for step in range(len(steps) - 1, -1, -1):
        k, pivot, around = steps[step]
        total = rhs[k]
        for j in around:
            total += around[j] * potential[j]
        potential[k] = total / pivot
    return potential


def grounded(
    edges: list[tuple[str, str, float]],
    front: set[str],
    nodes: list[str],
    source: str,
    amount: float,
) -> tuple[dict[str, float], dict[str, float]]:
    """Inject `amount` at `source` and read the current into each ready card (nemik:W871).

    nemik.flow's grounded nodal solve over plain floats. flow.py does it in exact Fractions, which
    need Python's unbounded integers; Codon's are 64 bits, so this port is in floats, and the tests
    hold it to the exact answer within a stated tolerance. The grounded Laplacian of a cone is
    symmetric and positive definite, so no pivoting.

    Args:
        edges: (card, prerequisite, conductance) for each dependency inside the cone.
        front: The ready cards, held at potential zero.
        nodes: The cone's cards.
        source: The card the demand enters at.
        amount: The demand injected there.

    Returns:
        (current into each ready card, the potential at every unknown node).

    """
    diag, link = _laplacian(edges, front, nodes)
    rhs: dict[str, float] = {}
    for node in diag:
        rhs[node] = amount if node == source else 0.0
    potential = _substitute(_eliminate(diag, link, rhs), rhs)
    into: dict[str, float] = {}
    for u, v, w in edges:
        for a, b in ((u, v), (v, u)):
            if b in front and a in potential:
                into[b] = into.get(b, 0.0) + w * potential[a]
    return into, potential


def _cone_edges(
    nodes: list[str], front: set[str], prereq: dict[str, list[str]], edge: float
) -> list[tuple[str, str, float]]:
    """List a cone's dependencies as edges of one conductance, as flow.solve builds them.

    Args:
        nodes: The cone's cards.
        front: The ready cards, which have no prerequisites in the model.
        prereq: card -> its open prerequisites.
        edge: The conductance of one dependency.

    Returns:
        (card, prerequisite, edge) for each dependency of a card that is not ready.

    """
    return [
        (card, prerequisite, edge)
        for card in nodes
        if card not in front
        for prerequisite in prereq.get(card, [])
    ]


def _has_ground(nodes: list[str], front: set[str]) -> bool:
    """Say whether a cone holds a ready card, which is where its demand can go.

    Args:
        nodes: The cone's cards.
        front: The ready cards.

    Returns:
        True when one of the cards is ready.

    """
    return any(node in front for node in nodes)


def salience(
    demand: dict[str, float],
    needs: dict[str, list[str]],
    front: set[str],
    edge: float = 1.0,
) -> tuple[dict[str, float], dict[str, float]]:
    """Propagate each source's demand to the ready frontier through its own cone (nemik:W872).

    nemik.flow.solve over plain floats, for the salience and the stranded demand: for every source
    in demand a nodal solve on its prerequisite cone (grounded), the current into each ready card
    summed over sources. A ready source absorbs its own demand; a source whose cone holds no ready
    card is stranded. Demand is conserved per source, to a relative tolerance of 1e-9, or it is a
    defect and raises.

    Args:
        demand: source card -> the demand it injects.
        needs: card -> its open prerequisites; a prerequisite named twice counts once.
        front: The ready cards.
        edge: The conductance of one dependency.

    Returns:
        (salience per ready card, stranded demand per source).

    Raises:
        ValueError: A source's demand is not conserved.

    """
    prereq: dict[str, list[str]] = {}
    for card, prerequisites in needs.items():
        if card not in front:
            prereq[card] = sorted(set(prerequisites))
    absorbed: dict[str, float] = {}
    stranded: dict[str, float] = {}
    for source in sorted(demand):
        amount = demand[source]
        if not amount:
            continue
        if source in front:
            absorbed[source] = absorbed.get(source, 0.0) + amount
            continue
        nodes = cone(prereq, front, source)
        if not _has_ground(nodes, front):
            stranded[source] = amount
            continue
        edges = _cone_edges(nodes, front, prereq, edge)
        into, _ = grounded(edges, front, nodes, source, amount)
        total = 0.0
        for card in sorted(into):
            absorbed[card] = absorbed.get(card, 0.0) + into[card]
            total += into[card]
        if abs(total - amount) > 1e-9 * max(1.0, abs(amount)):
            msg = f"demand at {source} is not conserved: {amount} in, {total} out"
            raise ValueError(msg)
    return absorbed, stranded


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
