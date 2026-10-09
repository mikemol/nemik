"""nemik:W238: demand flows from the cards that need something toward the ready frontier, conserved.

The model is gcalculus's conductance calculus read on nemik's queue graph (design note
W228-realizability-read-side.md, "Residue salience as effective conductance" and "The model is
DIRECTED"): parallel alternatives add, `OR(a, b) = a + b`; a chain composes in series,
`AND(a, b) = ab / (a + b)`, so it is never above its weakest link; a repeated source is counted once.

Direction is the queue's own: demand moves from a card to what it NEEDS (`blocked_on`) and is
absorbed at the ready frontier, so it can never reach a card the source does not need. A card with
several prerequisites does not split its demand by a rule fixed in advance (the operator ruled:
conserved, "let the physics do the work"). The solve runs from the frontier inward: each branch is its
edge in series with the prerequisite's own effective conductance, and the card's demand divides among
its branches in proportion. When a prerequisite lands it leaves `needs`, and the next solve divides
the same demand over what remains.

All arithmetic is exact `Fraction`, and every order is sorted, so the same input gives the same
answer bit for bit (nemik:W119). Cycles are reported, never dropped: a strongly connected component
needs its own small linear solve, which this first slice does not do.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

ZERO = Fraction(0)
ONE = Fraction(1)


class CycleError(ValueError):
    """The dependency graph has a cycle among these cards; none of them is solved."""

    def __init__(self, members: list[str]) -> None:
        super().__init__(f"dependency cycle among {', '.join(members)}")
        self.members = members


@dataclass(frozen=True)
class Flow:
    """One solve.

    `salience` is the demand each frontier card receives; `stranded` is demand that reached a card
    with no open prerequisite and no place on the frontier (a block on something outside the
    graph); `conductance` is each card's effective conductance to the frontier; `edges` is the demand
    carried by each (card, prerequisite) edge, the decomposition a mark keeps.
    """

    salience: dict[str, Fraction]
    stranded: dict[str, Fraction]
    conductance: dict[str, Fraction]
    edges: dict[tuple[str, str], Fraction]


def series(a: Fraction, b: Fraction) -> Fraction:
    """Compose two conductances in series (gcalculus AND): never above the weaker.

    Returns:
        ab / (a + b).

    """
    return a * b / (a + b)


def _order(
    needs: Mapping[str, Collection[str]], frontier: Collection[str]
) -> list[str]:
    """Order the non-frontier cards so every prerequisite precedes its dependents.

    Returns:
        the cards, prerequisites first.

    Raises:
        CycleError: when some cards can never be ordered.

    """
    pending = {
        card: {p for p in prereqs if p not in frontier}
        for card, prereqs in needs.items()
        if card not in frontier
    }
    for prereqs in list(pending.values()):
        for p in prereqs:
            pending.setdefault(p, {q for q in needs.get(p, ()) if q not in frontier})
    ordered: list[str] = []
    done: set[str] = set()
    while pending:
        ready = sorted(c for c, ps in pending.items() if ps <= done)
        if not ready:
            raise CycleError(sorted(pending))
        for card in ready:
            ordered.append(card)
            done.add(card)
            del pending[card]
    return ordered


def solve(
    demand: Mapping[str, Fraction],
    needs: Mapping[str, Collection[str]],
    frontier: Collection[str],
    edge: Fraction = ONE,
    sink: Fraction = ONE,
) -> Flow:
    """Propagate demand from its sources to the ready frontier.

    `needs[card]` lists the OPEN prerequisites of `card` (a landed or dropped one has left the list:
    an open circuit, never a zero weight). A prerequisite named twice counts once. `edge` is the
    conductance of every dependency edge and `sink` of every frontier card's tie to the sink; both
    are declared data (rank-weights.toml), here parameters.

    Returns:
        the salience, stranded demand, conductances and edge flows.

    """
    front = set(frontier)
    wanted = {c: sorted(set(ps)) for c, ps in needs.items() if c not in front}
    conductance: dict[str, Fraction] = dict.fromkeys(sorted(front), sink)
    shares: dict[str, dict[str, Fraction]] = {}
    order = _order(wanted, front)
    for card in order:
        branch = {
            p: series(edge, conductance[p])
            for p in wanted.get(card, [])
            if conductance.get(p, ZERO) > ZERO
        }
        total = sum(branch.values(), ZERO)
        conductance[card] = total
        shares[card] = (
            {p: b / total for p, b in sorted(branch.items())} if total else {}
        )
    inflow: dict[str, Fraction] = {}
    for card, amount in sorted(demand.items()):
        inflow[card] = inflow.get(card, ZERO) + amount
    edges: dict[tuple[str, str], Fraction] = {}
    stranded: dict[str, Fraction] = {}
    for card in reversed(order):
        amount = inflow.get(card, ZERO)
        if not amount:
            continue
        if not shares[card]:
            stranded[card] = amount
            continue
        for p, share in shares[card].items():
            edges[(card, p)] = amount * share
            inflow[p] = inflow.get(p, ZERO) + amount * share
    salience = {c: inflow[c] for c in sorted(front) if inflow.get(c, ZERO)}
    for card, amount in sorted(inflow.items()):
        if card not in front and card not in order and amount:
            stranded[card] = amount
    return Flow(salience, stranded, conductance, edges)
