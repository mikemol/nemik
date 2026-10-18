# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W692: blocked cards roll up under the node that dominates them in the blocked_on graph."""

from nemik.collapse import (
    Row,
    collapse,
    dominated_by,
    immediate_dominators,
    label,
    paths,
    violations,
)

NESTED: dict[str, Row] = {
    "P1": (["X"], ["Q1", "Q2"]),
    "P2": (["X"], ["Q3", "Q4"]),
    "Q1": (["P1"], []),
    "Q2": (["P1"], []),
    "Q3": (["P2"], []),
    "Q4": (["P2"], []),
}
DIAMOND: dict[str, Row] = {
    "A": (["B1", "B2"], []),
    "B1": (["C"], []),
    "B2": (["C"], []),
}


def test_cards_blocked_only_on_one_node_form_one_umbrella() -> None:
    """Three cards blocked on W9 alone collapse; a card blocked on W8 alone is a class of one."""
    blocked: dict[str, Row] = {
        "W1": (["W9"], []),
        "W2": (["W9"], []),
        "W3": (["W9"], []),
        "W4": (["W8"], []),
    }
    assert collapse(blocked) == [("W1_W9_u", ["W9"], [], ["W1", "W2", "W3"])]


def test_the_diamond_rolls_up_to_the_node_under_both_branches() -> None:
    """A waits on B1 and B2, which wait only on C: A, B1 and B2 all roll up under C."""
    got = collapse(DIAMOND)
    assert got == [("A_C_u", ["C"], [], ["A", "B1", "B2"])]
    idom = immediate_dominators(DIAMOND)
    assert idom["A"] == "C"
    assert dominated_by(idom, "A", "C")
    assert not dominated_by(idom, "A", "B1")


def test_cards_with_a_split_set_of_blockers_do_not_collapse() -> None:
    """Two cards blocked on W9 and W8, neither dominating them, have no node to roll up to."""
    blocked: dict[str, Row] = {"W1": (["W9", "W8"], []), "W2": (["W9", "W8"], [])}
    assert collapse(blocked) == []


def test_a_three_level_tree_nests_its_umbrellas_along_the_dominator_chain() -> None:
    """P1 and P2 sit under X and the Q pairs under P1 and P2; each umbrella nests in the last."""
    got = collapse(NESTED)
    assert [umbrella[0] for umbrella in got] == ["P1_X_u", "Q1_P1_u", "Q3_P2_u"]
    where = paths(NESTED, got)
    assert where["Q1"] == "P1_X_u/Q1_P1_u/Q1"
    assert where["Q4"] == "P1_X_u/Q3_P2_u/Q4"
    assert where["P2"] == "P1_X_u/P2"


def test_an_enables_edge_that_leaves_the_dominators_subtree_is_a_violation() -> None:
    """A1 is blocked only on C but enables R, which is not blocked behind C: it is left out."""
    blocked: dict[str, Row] = {
        "A1": (["C"], ["R"]),
        "A2": (["C"], []),
        "A3": (["C"], []),
    }
    assert violations(blocked) == [("A1", "C", "R")]
    assert collapse(blocked) == [("A2_C_u", ["C"], [], ["A2", "A3"])]


def test_a_blocked_on_cycle_does_not_loop_or_collapse() -> None:
    """Two cards that wait on each other have no way out of the graph, so no dominator."""
    blocked: dict[str, Row] = {"A": (["B"], []), "B": (["A"], [])}
    assert collapse(blocked) == []
    assert violations(blocked) == []


def test_the_label_names_the_count_the_blockers_and_what_they_enable() -> None:
    """The line the node and the Info share."""
    line = label(["W9"], ["W20"], ["W1", "W2"])
    assert line == "2 cards collapse under W9 (they enable W20)"
    bare = label([], [], ["W1", "W2"])
    assert bare == "2 cards collapse under nothing (they enable nothing)"
