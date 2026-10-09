"""nemik:W238: demand flows from the cards that need something to the ready frontier, conserved.

The model is gcalculus's (gcalculus:W208, `scripts/flow_reference.py`, b9196cf; design note
W228-realizability-read-side.md): for each demand source x, a NODAL solve on x's prerequisite closure
(x and everything it transitively needs), with the ready cards at potential 0 and the demand injected
at x. The current into each ready card is x's salience there; summed over sources it is the card's
salience, and per source it is the fibre a mark keeps.

Why a cone and why a nodal solve:
- Direction is the queue's own. Outside x's cone a coupling is a leak (a card x does not need would
  receive some of x's demand); inside it the coupling is real, the resource sensitivity: branches that
  share a prerequisite compete for its capacity.
- A series-parallel fold (parallel of series over the prerequisites) is the idempotent mistake: it
  counts a shared prerequisite once per branch. The nodal solve counts it once.
- The operator's conjunctive-split ruling needs no rule fixed in advance: the solve divides x's demand
  among its prerequisites, and divides it again when one lands and leaves `needs`.

The solve is exact sparse elimination (star-mesh, lowest degree first): the grounded Laplacian of a
cone is symmetric and positive definite, so no pivoting is needed, and the cones are nearly trees, so
the fill-in stays small (nemik:W250; the dense Gauss-Jordan it replaced cost 11 s over the fleet).
All arithmetic is exact `Fraction`, so the answer does not depend on the elimination order, and every
iteration is sorted (nemik:W119). Demand conserved is checked on every source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

ZERO = Fraction(0)
ONE = Fraction(1)


@dataclass(frozen=True)
class Flow:
    """One solve.

    `salience` is the demand each ready card absorbs, summed over sources; `fibre[card][source]` is
    the part that came from each source; `stranded` is the demand of a source with no ready card in
    its cone; `potential[source]` is the potential at the source for its injected demand, whose ratio
    to the demand is the effective resistance from the source to the frontier. `current[(card,
    prerequisite)]` is the demand that crossed that dependency, summed over sources (nemik:W264).
    """

    salience: dict[str, Fraction]
    fibre: dict[str, dict[str, Fraction]]
    stranded: dict[str, Fraction]
    potential: dict[str, Fraction]
    current: dict[tuple[str, str], Fraction] = field(default_factory=dict)


def _cone(
    needs: Mapping[str, Collection[str]], front: Collection[str], source: str
) -> list[str]:
    """Collect the source and everything it transitively needs; a ready card has no prerequisites.

    Returns:
        the cards, sorted.

    """
    seen: set[str] = set()
    stack = [source]
    while stack:
        card = stack.pop()
        if card in seen:
            continue
        seen.add(card)
        if card not in front:
            stack.extend(needs.get(card, ()))
    return sorted(seen)


def _grounded(
    edges: list[tuple[str, str, Fraction]],
    front: Collection[str],
    nodes: list[str],
    source: str,
    amount: Fraction,
) -> tuple[dict[str, Fraction], dict[str, Fraction]]:
    """Inject `amount` at `source` and read the current into each ready card.

    Eliminates the unknown nodes one at a time, lowest degree first (ties by name), keeping each
    node's pivot and neighbours for the back substitution.

    Returns:
        (current into each ready card, the potential at every unknown node; a ready card is 0).

    Raises:
        ZeroDivisionError: when a component has no ground (the pivot of its last node is zero).

    """
    diag: dict[str, Fraction] = {n: ZERO for n in nodes if n not in front}
    link: dict[str, dict[str, Fraction]] = {n: {} for n in diag}
    for u, v, w in edges:
        for a, b in ((u, v), (v, u)):
            if a in diag:
                diag[a] += w
                if b in diag:
                    link[a][b] = link[a].get(b, ZERO) + w
    rhs = {n: (amount if n == source else ZERO) for n in diag}
    steps: list[tuple[str, Fraction, dict[str, Fraction]]] = []
    while link:
        k = min(link, key=lambda n: (len(link[n]), n))
        pivot = diag[k]
        if pivot == 0:
            msg = "a component with no ground"
            raise ZeroDivisionError(msg)
        around = link.pop(k)
        for i, g_i in sorted(around.items()):
            diag[i] -= g_i * g_i / pivot
            rhs[i] += g_i / pivot * rhs[k]
            del link[i][k]
            for j, g_j in around.items():
                if j != i:
                    link[i][j] = link[i].get(j, ZERO) + g_i * g_j / pivot
        steps.append((k, pivot, around))
    potential: dict[str, Fraction] = {}
    for k, pivot, around in reversed(steps):
        potential[k] = (
            rhs[k] + sum((g * potential[j] for j, g in around.items()), ZERO)
        ) / pivot
    into: dict[str, Fraction] = {}
    for u, v, w in edges:
        for a, b in ((u, v), (v, u)):
            if b in front and a in potential:
                into[b] = into.get(b, ZERO) + w * potential[a]
    return into, potential


def solve(
    demand: Mapping[str, Fraction],
    needs: Mapping[str, Collection[str]],
    frontier: Collection[str],
    weights: Mapping[tuple[str, str], Fraction] | None = None,
    edge: Fraction = ONE,
) -> Flow:
    """Propagate each source's demand to the ready frontier through its own cone.

    `needs[card]` lists the OPEN prerequisites of `card` (a landed or dropped one has left the list:
    an open circuit, never a zero weight); a prerequisite named twice counts once. `weights[(card,
    prerequisite)]` overrides the conductance `edge` of one dependency; both are declared data
    (rank-weights.toml), here parameters.

    Returns:
        the salience, its fibre per source, the stranded sources and the source potentials.

    Raises:
        ValueError: when a source's demand is not conserved (a defect, never an expected answer).

    """
    front = set(frontier)
    prereq = {c: sorted(set(ps)) for c, ps in needs.items() if c not in front}
    fibre: dict[str, dict[str, Fraction]] = {}
    stranded: dict[str, Fraction] = {}
    potential: dict[str, Fraction] = {}
    current: dict[tuple[str, str], Fraction] = {}
    for source, amount in sorted(demand.items()):
        if not amount:
            continue
        if source in front:
            fibre.setdefault(source, {})[source] = amount
            continue
        cone = _cone(prereq, front, source)
        if not any(n in front for n in cone):
            stranded[source] = amount
            continue
        edges = [
            (u, p, (weights or {}).get((u, p), edge))
            for u in cone
            if u not in front
            for p in prereq.get(u, [])
        ]
        into, volts = _grounded(edges, front, cone, source, amount)
        potential[source] = volts.get(source, ZERO)
        if sum(into.values(), ZERO) != amount:
            msg = f"demand at {source} is not conserved: {amount} in, {sum(into.values(), ZERO)} out"
            raise ValueError(msg)
        for u, p, w in edges:
            across = w * (volts.get(u, ZERO) - volts.get(p, ZERO))
            if across:
                current[(u, p)] = current.get((u, p), ZERO) + across
        for card, absorbed in into.items():
            fibre.setdefault(card, {})[source] = absorbed
    salience = {
        card: sum(by_source.values(), ZERO)
        for card, by_source in sorted(fibre.items())
        if sum(by_source.values(), ZERO)
    }
    return Flow(
        salience,
        {c: dict(sorted(f.items())) for c, f in sorted(fibre.items())},
        stranded,
        potential,
        dict(sorted(current.items())),
    )
