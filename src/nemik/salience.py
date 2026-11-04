# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W238/W240: the flow model's salience of a repo's ready cards, beside downstream weight.

The graph side of nemik.flow, ported from gcalculus's audit script
(nemik/inbox/2026-10-09-gcalculus- w237-audit-script.md): the open graph, a card's prerequisites
(the reverse of what it moves), the ready frontier (open cards with no open prerequisite), and the
demand each waiting card in the ranked repo's downstream closure injects, weighted by the class it
carries relative to the ranked repo (local, peer, peer-blocked: the same `rank-weights.toml` classes
as the old arm). Edges are unit conductance, the baseline; the flow model replaces the old ranking
only after this audit (W241).
"""

from __future__ import annotations

import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from importlib.resources import files
from typing import TYPE_CHECKING, NamedTuple

from rdflib.namespace import PROV

from nemik.adapter import NEMIK, OSLC_CM
from nemik.flow import Flow, solve
from nemik.rank import (
    Weights,
    downstream_weight,
    load_weights,
    open_card,
    ref_of,
    repo_of,
    successors,
)
from nemik.tomlview import table

if TYPE_CHECKING:
    from collections.abc import Generator

    from rdflib import Graph
    from rdflib.term import Node

DECIMALS = 4

# nemik:W403: one document build asked for the same repo's solve up to four times (the ranking, the
# edge widths twice, the operator-ask weights), each a full flow solve over the same graph: 58
# solves, 245 of 268 profiled seconds. Inside `memo_audits()` an identical audit is answered from
# this table; outside it nothing is cached, so a CLI run computes exactly as before.
_MEMO: list[dict[tuple[object, ...], Audit] | None] = [None]


@contextmanager
def memo_audits() -> Generator[None]:
    """Answer repeated identical audits from a table for the duration of the block (one build)."""
    outer = _MEMO[0]
    _MEMO[0] = {} if outer is None else outer
    try:
        yield
    finally:
        _MEMO[0] = outer


@dataclass(frozen=True)
class Row:
    """One ready card of the ranked repo under both arms."""

    ref: str
    old: int
    new: Fraction


def _old_key(r: Row) -> tuple[int, int]:
    return (-r.old, _number(r.ref))


def _new_key(r: Row) -> tuple[Fraction, int]:
    return (-r.new, _number(r.ref))


def _need_key(item: tuple[str, Fraction]) -> tuple[Fraction, str]:
    return (-item[1], item[0])


@dataclass(frozen=True)
class Audit:
    """Both arms over one repo's ready cards, and the flow's own account of the solve."""

    rows: list[Row]
    flow: Flow
    sources: int
    demand: dict[str, Fraction] | None = None
    closures: dict[str, frozenset[str]] | None = None

    def contested(self, ref: str) -> list[tuple[str, Fraction, Fraction, list[str]]]:
        """List the sources in `ref`'s downstream closure whose demand is split with another card.

        A source is contested when more than one ready card absorbs it (a conjunctive diamond);
        each such source is why the flow salience of `ref` falls below its old weight.

        Returns:
            (source, demand, the part `ref` absorbs, the other cards sharing it), by source.

        """
        out: list[tuple[str, Fraction, Fraction, list[str]]] = []
        for source in sorted((self.closures or {}).get(ref, ())):
            sharers = sorted(c for c, by in self.flow.fibre.items() if source in by)
            if len(sharers) > 1 and ref in sharers:
                demand = (self.demand or {}).get(source, Fraction(0))
                others = [c for c in sharers if c != ref]
                out.append((source, demand, self.flow.fibre[ref][source], others))
        return out

    def old_order(self) -> list[str]:
        """Order the cards by the old weight, the lower symbol first on a tie.

        Returns:
            the card refs.

        """
        return [r.ref for r in sorted(self.rows, key=_old_key)]

    def new_order(self) -> list[str]:
        """Order the cards by the flow salience, the lower symbol first on a tie.

        Returns:
            the card refs.

        """
        return [r.ref for r in sorted(self.rows, key=_new_key)]

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


def _node_number(n: Node) -> int:
    return _number(ref_of(n))


def _memo_key(
    g: Graph, repo: str, weights: Weights, extra: tuple[object, ...]
) -> tuple[object, ...]:
    """Give the memo key of one audit call (nemik:W403).

    Returns:
        the graph identity and size, the repo, the four class weights and the per-call inputs.

    """
    return (
        id(g),
        len(g),
        repo,
        weights.local,
        weights.peer,
        weights.peer_blocked,
        weights.operator,
        *extra,
    )


def _open_graph(
    g: Graph, *, workable: bool
) -> tuple[set[Node], dict[Node, set[Node]], set[Node]]:
    """Read the open cards, what each waits for and which have nothing to wait for.

    Returns:
        the open cards, their open prerequisites and the ready ground (narrowed to ready or
        working cards when `workable`).

    """
    nodes = {n for n in g.subjects(OSLC_CM.state, None) if open_card(g, n)}
    prereq: dict[Node, set[Node]] = {}
    for p in nodes:
        for s in successors(g, p):
            if s in nodes and s != p:
                prereq.setdefault(s, set()).add(p)
    ready = {n for n in nodes if n not in prereq}
    if workable:
        ready = {
            n
            for n in ready
            if (n, OSLC_CM.state, NEMIK.Ready) in g
            or (n, OSLC_CM.state, NEMIK.Working) in g
        }
    return nodes, prereq, ready


def _cone(g: Graph, n: Node, nodes: set[Node]) -> set[Node]:
    """Walk the open successors of `n`.

    Returns:
        every open card downstream of `n`, not `n` itself.

    """
    seen, stack = {n}, [n]
    while stack:
        for nxt in successors(g, stack.pop()):
            if nxt not in seen and nxt in nodes:
                seen.add(nxt)
                stack.append(nxt)
    return seen - {n}


def _reach(
    g: Graph, mine: list[Node], nodes: set[Node]
) -> tuple[set[Node], dict[str, frozenset[str]]]:
    """Take the cone of each ranked card.

    Returns:
        the union of the cones and each card's own cone by ref.

    """
    population: set[Node] = set()
    reach: dict[str, frozenset[str]] = {}
    for n in mine:
        cone = _cone(g, n, nodes)
        population |= cone
        reach[ref_of(n)] = frozenset(ref_of(x) for x in cone)
    return population, reach


def _class_demand(
    g: Graph, sources: list[Node], weights: Weights, repo: str, without: str
) -> dict[str, Fraction]:
    """Give each source the class weight of its repo and state.

    Returns:
        the demand by ref, leaving out the source `without` names.

    """

    def klass(x: Node) -> int:
        if repo_of(x) == repo:
            return weights.local
        return (
            weights.peer_blocked
            if (x, OSLC_CM.state, NEMIK.Blocked) in g
            else weights.peer
        )

    return {ref_of(x): Fraction(klass(x)) for x in sources if ref_of(x) != without}


def _add_operator_demand(
    g: Graph,
    demand: dict[str, Fraction],
    nodes: set[Node],
    scope: tuple[set[str], str],
    amount: int,
) -> None:
    """Add the operator class weight to each card an operator asked for (nemik:W249).

    An operator ask is a demand source with a declared class weight, not a strict tier above the
    order. A ready ask absorbs its own demand; a waiting one sends it through its cone. Additive
    to the class weight the card already carries.
    """
    relevant, without = scope
    for n in sorted(nodes, key=str):
        cause = str(g.value(n, PROV.wasInformedBy) or "").strip().lower()
        asked = cause == "operator" or cause.startswith("operator:")
        if asked and ref_of(n) in relevant and ref_of(n) != without:
            demand[ref_of(n)] = demand.get(ref_of(n), Fraction(0)) + amount


def _apply_residue(
    demand: dict[str, Fraction],
    needs: dict[str, list[str]],
    residue: dict[str, list[dict[str, object]]],
    scope: tuple[set[str], set[str], set[str], str],
    gates: tuple[dict[str, Fraction] | None, Fraction],
) -> None:
    """Inject each recorded gap's demand at its card (nemik:W251).

    An entry that names an open `closes_ref` adds that card to the prerequisites, so the card that
    closes the gap is pulled up.
    """
    open_refs, relevant, front, without = scope
    gate_weights, gate_weight = gates
    for card, entries in residue.items():
        if card not in open_refs or card not in relevant or card == without:
            continue
        for entry in entries:
            weight = (gate_weights or {}).get(str(entry.get("gate")), gate_weight)
            demand[card] = demand.get(card, Fraction(0)) + weight
            target = entry.get("closes_ref")
            if (
                isinstance(target, str)
                and target in open_refs
                and target != card
                and card not in front
            ):
                needs[card] = sorted({*needs.get(card, []), target})


class AuditOptions(NamedTuple):
    """What audit may be asked besides the graph: what to leave out, the gaps, the weights."""

    without: str = ""
    residue: dict[str, list[dict[str, object]]] | None = None
    gate_weight: Fraction = Fraction(1)
    workable: bool = False
    gate_weights: dict[str, Fraction] | None = None
    toward: str = ""
    wait_weight: Fraction = Fraction(0)


NO_OPTIONS = AuditOptions()


def audit(
    g: Graph,
    repo: str,
    weights: Weights | None = None,
    *,
    options: AuditOptions = NO_OPTIONS,
) -> Audit:
    """Run both arms over the ready cards of `repo`.

    `wait_weight` (nemik:W699) adds that much demand per loop tick a waiting source has been
    blocked, so the cards it waits on rank higher the longer the wait; zero leaves the flow
    as it was.

    `toward` (`repo:W<n>`, nemik:W316) makes the one demand source the named milestone: salience
    then reads as what moves that card, with no operator or residue demand added.

    `workable` narrows the ground to cards whose state is ready or working. By default the ground
    is gcalculus's: every open card with no open prerequisite, which includes a card blocked on
    something outside the graph (an operator ask, another agent); such a card then absorbs demand
    that a workable card would otherwise receive.

    `weights` default to the packaged `rank-weights.toml` classes. `without` names one source whose
    demand is left out of the flow arm, to see what that source contributes (nemik:W244).

    `residue` maps a card (`repo:W<n>`) to its recorded gaps (the policy's residue entries, nemik:
    W251): each entry injects `gate_weight` of demand at its card. A ready card absorbs its own;
    a waiting card's demand flows through its cone, and an entry that names an open `closes_ref`
    adds that card to the prerequisites, so the card that closes the gap is pulled up. Absent, the
    flow is the class-weighted downstream demand only.

    Returns:
        the rows (ready cards of `repo`, in symbol order), the flow solve and the source count.

    """
    weights = weights or load_weights()
    # W403: residue and gate weights are per-call inputs, not part of the key, so those audits
    # bypass it.
    key: tuple[object, ...] | None = None
    if (
        _MEMO[0] is not None
        and options.residue is None
        and options.gate_weights is None
    ):
        key = _memo_key(
            g,
            repo,
            weights,
            (
                options.without,
                options.gate_weight,
                options.workable,
                options.toward,
                options.wait_weight,
            ),
        )
        if key in _MEMO[0]:
            return _MEMO[0][key]
    nodes, prereq, ready = _open_graph(g, workable=options.workable)
    mine = sorted((n for n in ready if repo_of(n) == repo), key=_node_number)
    population, reach = _reach(g, mine, nodes)
    sources = sorted((x for x in population if x in prereq), key=str)
    if options.toward:
        # nemik:W316: a milestone ranks by ITS demand alone: the one source is the target card.
        sources = [x for x in sources if ref_of(x) == options.toward]
    needs = {
        ref_of(x): sorted(ref_of(p) for p in ps if p in nodes)
        for x, ps in prereq.items()
    }
    demand = _class_demand(g, sources, weights, repo, options.without)
    front = {ref_of(n) for n in ready}
    relevant = {ref_of(x) for x in population} | {ref_of(n) for n in mine}
    if weights.operator and not options.toward:
        _add_operator_demand(
            g, demand, nodes, (relevant, options.without), weights.operator
        )
    for card, added in wait_demand(
        g, sources, options.wait_weight, options.without
    ).items():
        demand[card] = demand.get(card, Fraction(0)) + added
    if not options.toward:
        _apply_residue(
            demand,
            needs,
            options.residue or {},
            ({ref_of(n) for n in nodes}, relevant, front, options.without),
            (options.gate_weights, options.gate_weight),
        )
    flow = solve(demand, needs, front)
    result = Audit(
        [
            Row(
                ref_of(n),
                downstream_weight(g, n, weights),
                flow.salience.get(ref_of(n), Fraction(0)),
            )
            for n in mine
        ],
        flow,
        len(sources),
        demand,
        reach,
    )
    if key is not None and _MEMO[0] is not None:
        _MEMO[0][key] = result
    return result


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
    bare = audit(g, repo, weights, options=AuditOptions(without=ref))
    before = {c: i for i, c in enumerate(bare.new_order())}
    after = {c: i for i, c in enumerate(full.new_order())}
    displaced = [
        (c, before[c] + 1, after[c] + 1) for c in sorted(after) if after[c] > before[c]
    ]
    needs = sorted(absorbed, key=_need_key)
    return AskEffect(ref, needs, displaced, stranded)


def table_weights(name: str, text: str | None = None) -> dict[str, Fraction]:
    """Read one numeric table of rank-weights.toml as exact fractions.

    Args:
        name: The table's name.
        text: The rank-weights TOML, or None for the one that ships with the package.

    Returns:
        The table's entries; empty when the table is absent.

    """
    if text is None:
        text = files("nemik.data").joinpath("rank-weights.toml").read_text()
    parsed: object = tomllib.loads(text)
    entries = table(table(parsed).get(name))
    return {str(gate): Fraction(str(w)) for gate, w in entries.items()}


def load_gate_weights(text: str | None = None) -> dict[str, Fraction]:
    """Read the per-gate residue weights from `[residue]` in rank-weights.toml (nemik:W253).

    `text` overrides the packaged file (for tests). A gate the table does not name weighs 1.

    Returns:
        the weight of one residue entry at each named gate.

    """
    return table_weights("residue", text)


def load_wait_weight(text: str | None = None) -> Fraction:
    """Read what one loop tick of waiting adds to demand from `[wait_age]` in rank-weights.toml.

    nemik:W699: a card that has waited longer on its blockers asks harder. Absent or zero means
    waiting adds nothing, which is the ranking as it was.

    Args:
        text: The rank-weights TOML, or None for the one that ships with the package.

    Returns:
        The demand one tick of a card's `ticks_blocked` adds; zero when the table is absent.

    """
    return table_weights("wait_age", text).get("per_tick", Fraction(0))


def wait_demand(
    g: Graph, sources: list[Node], wait_weight: Fraction, without: str = ""
) -> dict[str, Fraction]:
    """Give the demand each waiting source adds for the ticks it has been blocked.

    A source that waits injects demand that flows through its cone to the cards it waits on, so a
    blocker's salience rises with the age of the waits on it (nemik:W699).

    Args:
        g: The merged queue graph.
        sources: The waiting cards that inject demand.
        wait_weight: The demand one tick adds (load_wait_weight).
        without: A card whose demand is left out.

    Returns:
        card -> added demand, only for cards that have waited at least one tick.

    """
    added: dict[str, Fraction] = {}
    if not wait_weight:
        return added
    for node in sources:
        ticks = int(str(g.value(node, NEMIK.ticksBlocked) or 0))
        if ticks and ref_of(node) != without:
            added[ref_of(node)] = wait_weight * ticks
    return added


def salience_of(
    g: Graph,
    repo: str,
    weights: Weights,
    *,
    toward: str = "",
) -> dict[str, Fraction]:
    """Solve `repo`'s ready cards and return each card's exact flow salience, by `repo:W<n>`.

    The class weights are those of `rank-weights.toml` (`operator` being what an operator ask
    injects, W249); nemik.rank uses this for its `weight` objective (W241).

    The ground is the WORKABLE cards (state ready or working), what a worker can pick up now: a card
    blocked on something outside the graph is a dead end and absorbs nothing (nemik:W252; measured
    against the open ground, 0 of 10,011 luthen pairs and 5 of 4,753 paperkit pairs order
    differently).

    Returns:
        the salience of every workable card of `repo` that absorbs any demand.

    """
    return audit(
        g,
        repo,
        weights,
        options=AuditOptions(workable=True, toward=toward),
    ).flow.salience


def edge_currents(
    g: Graph,
    repo: str,
    weights: Weights,
    *,
    workable: bool = True,
) -> dict[tuple[str, str], float]:
    """Give the demand across each dependency in `repo`'s solve, by (needing card, prerequisite).

    Each key is the `repo:W<n>` of the card that needs and of its prerequisite: what the view draws
    as an edge's width (nemik:W264). Floats: the view needs a magnitude, not the exact fraction.
    `workable` False takes the open ground, so the edges into an operator ask (a card waiting
    outside the graph) carry their current too (W298).

    Returns:
        The demand on each dependency as a float, keyed by (needing card,
        prerequisite).

    """
    flow = audit(g, repo, weights, options=AuditOptions(workable=workable)).flow
    return {edge: float(amount) for edge, amount in flow.current.items()}
