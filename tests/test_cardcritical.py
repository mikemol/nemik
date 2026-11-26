# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W976: cardcritical's cycles over plain successors equal critical.cycles over the graph."""

from __future__ import annotations

from itertools import pairwise, product

from rdflib import Graph, Literal, URIRef

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.cardcritical import cycles_of
from nemik.cards import cards
from nemik.critical import cycles

DEEP = 3000  # a chain longer than a recursive walk would take
CARDS = 3  # the cards of the small graphs checked over every edge set


def _card(g: Graph, sym: str, status: str = "ready") -> URIRef:
    node = waypoint_uri("a", sym)
    g.add((node, OSLC_CM.state, STATE[status]))
    return node


def _plain(g: Graph) -> tuple[dict[str, list[str]], set[str]]:
    # the successor lists and the operator-blocked set the way the adapter would hand them over
    by_cite = cards(g)
    open_cites = {c for c, card in by_cite.items() if not card.done}
    succ: dict[str, list[str]] = {c: [] for c in sorted(open_cites)}
    for cite in sorted(open_cites):
        for before in (*by_cite[cite].enabled_by, *by_cite[cite].waits_for):
            if before in open_cites and cite not in succ[before]:
                succ[before].append(cite)
    human = {
        c
        for c in open_cites
        if (waypoint_uri("a", c.split(":")[1]), NEMIK.blockedKind, Literal("human"))
        in g
    }
    return {c: sorted(s) for c, s in succ.items()}, human


def test_the_cycles_equal_the_graph_version_on_the_fixture() -> None:
    """A ring x -> y -> z -> x and a self-wait are cycles, a -> b is a chain; an ask flags."""
    g = Graph()
    x, y, z, a, b, w = (_card(g, s) for s in ("W1", "W2", "W3", "W4", "W5", "W6"))
    for src, dst in ((x, y), (y, z), (z, x), (a, b), (w, w)):
        g.add((src, NEMIK.enables, dst))
    succ, human = _plain(g)
    assert cycles_of(succ, human) == cycles(g)
    g.add((y, NEMIK.blockedKind, Literal("human")))
    succ, human = _plain(g)
    assert cycles_of(succ, human) == cycles(g)
    assert cycles_of(succ, human)[0] == (["a:W1", "a:W2", "a:W3"], True)


def test_every_small_graph_agrees_with_the_graph_version() -> None:
    """All edge sets over three cards (self-waits included), with and without a done card."""
    pairs = list(product(range(CARDS), range(CARDS)))
    for mask in range(1 << len(pairs)):
        for done_last in (False, True):
            g = Graph()
            nodes = [
                _card(
                    g, f"W{i + 1}", "done" if done_last and i == CARDS - 1 else "ready"
                )
                for i in range(CARDS)
            ]
            for bit, (src, dst) in enumerate(pairs):
                if mask >> bit & 1:
                    g.add((nodes[src], NEMIK.enables, nodes[dst]))
            succ, human = _plain(g)
            assert cycles_of(succ, human) == cycles(g), (mask, done_last)


def test_a_long_chain_and_its_closing_edge_do_not_meet_a_recursion_limit() -> None:
    """A chain of DEEP cards is no cycle; closing it makes one component of all of them."""
    names = [f"a:W{i}" for i in range(1, DEEP + 1)]
    succ = {name: [nxt] for name, nxt in pairwise(names)}
    succ[names[-1]] = []
    assert cycles_of(succ, set()) == []
    succ[names[-1]] = [names[0]]
    found = cycles_of(succ, set())
    assert len(found) == 1
    assert found[0] == (sorted(names), False)


def test_a_card_cite_is_never_empty_and_an_empty_name_is_refused() -> None:
    """The DONE sentinel is the empty string, so no empty name may reach cycles_of."""
    g = Graph()
    _card(g, "W1")
    _card(g, "W2")
    assert all(cite for cite in cards(g))
    refused = []
    for bad in ({"": ["a:W1"]}, {"a:W1": [""]}):
        try:
            cycles_of(bad, set())
        except ValueError as error:
            refused.append(str(error))
    assert refused == ["a card with an empty name"] * len(refused)
    assert len(refused) == len(("as a card", "as a successor"))


def test_a_card_with_no_entry_has_no_successors() -> None:
    """A successor named but absent as a key is a leaf, not an error."""
    assert cycles_of({"a:W1": ["a:W2"]}, set()) == []
