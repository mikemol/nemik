# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W436: a ready umbrella over two or more open children of its own is flagged.

A chain step is not flagged.

nemik:W529: ReadyUmbrellaShape is a SPARQL constraint in shapes.ttl over the enables edges.
"""

from itertools import count

from rdflib import RDF, Graph
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, waypoint_uri, workstream_uri
from nemik.blocks import annotate
from nemik.check import shapes
from nemik.shaclinc import findings

_KEYS = count()


def _card(g: Graph, repo: str, symbol: str, state: Node) -> Node:
    """Add a card in a state to a repo.

    Args:
        g: The graph to add to.
        repo: The repo's name.
        symbol: The card's symbol.
        state: Its OSLC state.

    Returns:
        The card's node.

    """
    node = waypoint_uri(repo, symbol)
    g.add((node, RDF.type, OSLC_CM.ChangeRequest))
    g.add((node, OSLC_CM.state, state))
    g.add((node, NEMIK.workstream, workstream_uri(repo)))
    return node


def _graph(child_states: list[Node]) -> Graph:
    """Build a ready W1 with one child per state, each enabling it.

    Args:
        child_states: The children's states.

    Returns:
        The graph.

    """
    g = Graph()
    top = _card(g, "r", "W1", NEMIK.Ready)
    for i, state in enumerate(child_states, start=2):
        g.add((_card(g, "r", f"W{i}", state), NEMIK.enables, top))
    return g


def _flagged(g: Graph) -> set[Node]:
    """Collect the cards ReadyUmbrellaShape names.

    Args:
        g: The graph.

    Returns:
        The named cards.

    """
    annotate(g)
    rows = findings(f"ready-umbrella-{next(_KEYS)}", g, shapes())
    return {focus for focus, _, m in rows if m.startswith("ready, but an umbrella")}


def test_a_ready_card_with_two_open_children_is_flagged() -> None:
    """Two open children make the ready W1 an umbrella."""
    g = _graph([NEMIK.Ready, NEMIK.Blocked])
    assert _flagged(g) == {waypoint_uri("r", "W1")}


def test_one_open_child_is_a_chain_step_not_an_umbrella() -> None:
    """One open child and one done: a step in a chain."""
    assert _flagged(_graph([NEMIK.Ready, NEMIK.Done])) == set()


def test_a_blocked_umbrella_is_not_flagged() -> None:
    """A blocked umbrella is already waiting on its children."""
    g = _graph([NEMIK.Ready, NEMIK.Ready])
    top = waypoint_uri("r", "W1")
    g.set((top, OSLC_CM.state, NEMIK.Blocked))
    assert _flagged(g) == set()


def test_children_in_another_repo_do_not_count() -> None:
    """Only a card's own repo's open cards make it an umbrella."""
    g = Graph()
    top = _card(g, "r", "W1", NEMIK.Ready)
    for i in (2, 3):
        g.add((_card(g, "other", f"W{i}", NEMIK.Ready), NEMIK.enables, top))
    assert _flagged(g) == set()
