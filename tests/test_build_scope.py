# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W518: building the static view inside one build's index scope changes how fast, never what.

A warm publish profiled at 94 s with a third of it in rank.goals asking rdflib for facts the
per-graph
index (nemik:W412) holds, because the static build ran outside the scope the live server's document
is
built in. The scope and the cards() memo are optimizations, so every published byte must be the
same.
"""

from pathlib import Path

from rdflib import Graph
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, waypoint_uri
from nemik.cards import cards
from nemik.index import indexed
from nemik.serve import _build_static, build_static

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_the_scoped_build_publishes_exactly_what_the_unscoped_one_does(
    tmp_path: Path,
) -> None:
    """The scoped build publishes exactly what the unscoped one does."""
    unscoped, scoped = tmp_path / "unscoped", tmp_path / "scoped"
    _build_static(FLEET, unscoped, None, True)
    build_static(FLEET, scoped, None, True)
    a, b = _tree(unscoped), _tree(scoped)
    assert a.keys() == b.keys()
    different = [name for name in a if a[name] != b[name] and name != "metrics"]
    assert different == [], f"differ: {different[:5]}"
    assert len(a) > 20, "the fixture fleet published almost nothing"


def _graph(state: Node) -> Graph:
    g = Graph()
    g.add((waypoint_uri("r", "W1"), OSLC_CM.state, state))
    return g


def test_cards_are_read_once_per_graph_inside_a_scope_and_never_stale_outside() -> None:
    """Cards are read once per graph inside a scope and never stale outside."""
    g = _graph(NEMIK.Ready)
    with indexed():
        first, second = cards(g), cards(g)
        assert first == second and first is not second, (
            "a shared dict would let a caller edit it"
        )
        assert first["r:W1"].state == "ready"
    # outside any scope nothing is cached: a graph changed between asks is read afresh
    g.set((waypoint_uri("r", "W1"), OSLC_CM.state, NEMIK.Done))
    assert cards(g)["r:W1"].state == "done"
