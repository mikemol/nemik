"""nemik:W238/W240: the flow model's salience of a repo's ready cards, beside the old downstream weight.

The graph side of nemik.flow, ported from gcalculus's audit script (nemik/inbox/2026-10-09-gcalculus-
w237-audit-script.md): the open graph, a card's prerequisites (the reverse of what it moves), the
ready frontier (open cards with no open prerequisite), and the demand each waiting card in the ranked
repo's downstream closure injects, weighted by the class it carries relative to the ranked repo
(local, peer, peer-blocked: the same `rank-weights.toml` classes as the old arm). Edges are unit
conductance, the baseline; the flow model replaces the old ranking only after this audit (W241).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

from nemik.adapter import NEMIK, OSLC_CM
from nemik.flow import Flow, solve
from nemik.rank import _open, _repo, downstream_weight, ref_of, successors

if TYPE_CHECKING:
    from rdflib import Graph
    from rdflib.term import Node

    from nemik.rank import Weights

DECIMALS = 4


@dataclass(frozen=True)
class Row:
    """One ready card of the ranked repo under both arms."""

    ref: str
    old: int
    new: Fraction


@dataclass(frozen=True)
class Audit:
    """Both arms over one repo's ready cards, and the flow's own account of the solve."""

    rows: list[Row]
    flow: Flow
    sources: int

    def old_order(self) -> list[str]:
        """Order the cards by the old weight, the lower symbol first on a tie.

        Returns:
            the card refs.

        """
        return [
            r.ref for r in sorted(self.rows, key=lambda r: (-r.old, _number(r.ref)))
        ]

    def new_order(self) -> list[str]:
        """Order the cards by the flow salience, the lower symbol first on a tie.

        Returns:
            the card refs.

        """
        return [
            r.ref for r in sorted(self.rows, key=lambda r: (-r.new, _number(r.ref)))
        ]

    def disagreements(self) -> list[tuple[str, str]]:
        """List the pairs the old weight strictly orders one way and the flow the other.

        Returns:
            (a, b) where the old weight puts a above b and the flow salience puts b above a.

        """
        out: list[tuple[str, str]] = []
        for i, a in enumerate(self.rows):
            for b in self.rows[i + 1 :]:
                hi, lo = (a, b) if a.old > b.old else (b, a)
                if hi.old != lo.old and hi.new < lo.new:
                    out.append((hi.ref, lo.ref))
        return sorted(out)


def _number(ref: str) -> int:
    return int(ref.rsplit("W", 1)[1])


def show(value: Fraction, places: int = DECIMALS) -> str:
    """Round an exact salience for display only; comparison stays exact.

    Returns:
        the value to `places` decimals.

    """
    return f"{float(value):.{places}f}"


def audit(
    g: Graph, repo: str, weights: Weights | None = None, without: str = ""
) -> Audit:
    """Run both arms over the ready cards of `repo`.

    `weights` default to the packaged `rank-weights.toml` classes. `without` names one source whose
    demand is left out of the flow arm, to see what that source contributes (nemik:W244).

    Returns:
        the rows (ready cards of `repo`, in symbol order), the flow solve and the source count.

    """
    from nemik.rank import load_weights

    weights = weights or load_weights()
    nodes = {n for n in g.subjects(OSLC_CM.state, None) if _open(g, n)}
    prereq: dict[Node, set[Node]] = {}
    for p in nodes:
        for s in successors(g, p):
            if s in nodes and s != p:
                prereq.setdefault(s, set()).add(p)
    ready = {n for n in nodes if n not in prereq}
    mine = sorted(
        (n for n in ready if _repo(n) == repo), key=lambda n: _number(ref_of(n))
    )

    def klass(x: Node) -> int:
        if _repo(x) == repo:
            return weights.local
        return (
            weights.peer_blocked
            if (x, OSLC_CM.state, NEMIK.Blocked) in g
            else weights.peer
        )

    def closure(n: Node) -> set[Node]:
        seen, stack = {n}, [n]
        while stack:
            for nxt in successors(g, stack.pop()):
                if nxt not in seen and nxt in nodes:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen - {n}

    population: set[Node] = set()
    for n in mine:
        population |= closure(n)
    sources = sorted((x for x in population if x in prereq), key=str)
    needs = {
        ref_of(x): sorted(ref_of(p) for p in ps if p in nodes)
        for x, ps in prereq.items()
    }
    demand = {ref_of(x): Fraction(klass(x)) for x in sources if ref_of(x) != without}
    flow = solve(demand, needs, {ref_of(n) for n in ready})
    rows = [
        Row(
            ref_of(n),
            downstream_weight(g, n, weights),
            flow.salience.get(ref_of(n), Fraction(0)),
        )
        for n in mine
    ]
    return Audit(rows, flow, len(sources))


@dataclass(frozen=True)
class AskEffect:
    """What one waiting card (an operator ask is one) needs and what it displaces.

    `needs` is where its demand lands: each ready card that absorbs part of it, with the current,
    largest first (its path to the frontier). `displaced` lists the ready cards of the ranked repo
    that sit lower with this source's demand than without it: (card, position without, position
    with). Nothing here is a policy: the ask is already a demand source in the model.
    """

    ref: str
    needs: list[tuple[str, Fraction]]
    displaced: list[tuple[str, int, int]]
    stranded: bool


def ask_effect(
    g: Graph, repo: str, ref: str, weights: Weights | None = None
) -> AskEffect:
    """Show what `ref` needs and which of `repo`'s ready cards it pushes down.

    Returns:
        the effect, whose `needs` is empty and `stranded` true when no ready card is in its cone.

    Raises:
        ValueError: when `ref` injects no demand into `repo`'s ranking (it is not in the downstream
            closure of any ready card of `repo`).

    """
    full = audit(g, repo, weights)
    absorbed = [
        (card, by_source[ref])
        for card, by_source in full.flow.fibre.items()
        if ref in by_source
    ]
    stranded = ref in full.flow.stranded
    if not absorbed and not stranded:
        msg = f"{ref} injects no demand into {repo}'s ranking"
        raise ValueError(msg)
    bare = audit(g, repo, weights, without=ref)
    before = {c: i for i, c in enumerate(bare.new_order())}
    after = {c: i for i, c in enumerate(full.new_order())}
    displaced = [
        (c, before[c] + 1, after[c] + 1) for c in sorted(after) if after[c] > before[c]
    ]
    needs = sorted(absorbed, key=lambda item: (-item[1], item[0]))
    return AskEffect(ref, needs, displaced, stranded)
