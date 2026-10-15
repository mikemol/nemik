# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W436: a ready umbrella over two or more open children of its own is flagged; a chain step is not."""

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, waypoint_uri
from nemik.blocks import annotate


def _graph(child_states: list) -> Graph:
    g = Graph()
    top = waypoint_uri("r", "W1")
    g.add((top, OSLC_CM.state, NEMIK.Ready))
    for i, state in enumerate(child_states, start=2):
        kid = waypoint_uri("r", f"W{i}")
        g.add((kid, OSLC_CM.state, state))
        g.add((kid, NEMIK.enables, top))
    return g


def _flagged(g: Graph) -> set:
    annotate(g)
    return set(g.subjects(NEMIK.readyUmbrella, None))


def test_a_ready_card_with_two_open_children_is_flagged() -> None:
    g = _graph([NEMIK.Ready, NEMIK.Blocked])
    assert _flagged(g) == {waypoint_uri("r", "W1")}


def test_one_open_child_is_a_chain_step_not_an_umbrella() -> None:
    assert _flagged(_graph([NEMIK.Ready, NEMIK.Done])) == set()


def test_a_blocked_umbrella_is_not_flagged() -> None:
    g = _graph([NEMIK.Ready, NEMIK.Ready])
    top = waypoint_uri("r", "W1")
    g.set((top, OSLC_CM.state, NEMIK.Blocked))
    assert _flagged(g) == set()


def test_children_in_another_repo_do_not_count() -> None:
    g = Graph()
    top = waypoint_uri("r", "W1")
    g.add((top, OSLC_CM.state, NEMIK.Ready))
    for i in (2, 3):
        kid = waypoint_uri("other", f"W{i}")
        g.add((kid, OSLC_CM.state, NEMIK.Ready))
        g.add((kid, NEMIK.enables, top))
    assert _flagged(g) == set()
