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

All arithmetic is exact `Fraction`, so the answer does not depend on an elimination order, and every
iteration is sorted (nemik:W119). Demand conserved is checked on every source.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    to the demand is the effective resistance from the source to the frontier.
    """

    salience: dict[str, Fraction]
    fibre: dict[str, dict[str, Fraction]]
    stranded: dict[str, Fraction]
    potential: dict[str, Fraction]


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


def _solve(matrix: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    """Solve a linear system exactly, by Gauss-Jordan elimination over the rationals.

    Returns:
        the solution.

    Raises:
        ZeroDivisionError: when the system is singular (a component with no ground).

    """
    n = len(matrix)
    rows = [[*row, rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if rows[r][col] != 0), None)
        if pivot is None:
            msg = "a component with no ground"
            raise ZeroDivisionError(msg)
        rows[col], rows[pivot] = rows[pivot], rows[col]
        scale = rows[col][col]
        rows[col] = [v / scale for v in rows[col]]
        for r in range(n):
            if r != col and rows[r][col] != 0:
                factor = rows[r][col]
                rows[r] = [
                    a - factor * b for a, b in zip(rows[r], rows[col], strict=True)
                ]
    return [rows[i][n] for i in range(n)]


def _grounded(
    edges: list[tuple[str, str, Fraction]],
    front: Collection[str],
    nodes: list[str],
    source: str,
    amount: Fraction,
) -> tuple[dict[str, Fraction], Fraction]:
    """Inject `amount` at `source` and read the current into each ready card.

    Returns:
        (current into each ready card, the potential at the source).

    """
    unknown = [n for n in nodes if n not in front]
    index = {n: i for i, n in enumerate(unknown)}
    size = len(unknown)
    matrix = [[ZERO] * size for _ in range(size)]
    for u, v, w in edges:
        for a, b in ((u, v), (v, u)):
            if a in index:
                matrix[index[a]][index[a]] += w
                if b in index:
                    matrix[index[a]][index[b]] -= w
    rhs = [amount if n == source else ZERO for n in unknown]
    potential = dict(zip(unknown, _solve(matrix, rhs), strict=True))
    into: dict[str, Fraction] = {}
    for u, v, w in edges:
        for a, b in ((u, v), (v, u)):
            if b in front and a in potential:
                into[b] = into.get(b, ZERO) + w * potential[a]
    return into, potential.get(source, ZERO)


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
        into, potential[source] = _grounded(edges, front, cone, source, amount)
        if sum(into.values(), ZERO) != amount:
            msg = f"demand at {source} is not conserved: {amount} in, {sum(into.values(), ZERO)} out"
            raise ValueError(msg)
        for card, current in into.items():
            fibre.setdefault(card, {})[source] = current
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
    )
