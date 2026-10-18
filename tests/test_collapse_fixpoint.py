# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W692: the operator's recursive cases reach a fixed point of the dominator rule.

695f3e0a line 80661: with A blocked on C and on B1, and B1 blocked only on C, A rolls up to C too.
"""

from nemik.collapse import (
    Row,
    collapse,
    disagreements,
    immediate_dominators,
    paths,
    waits_on,
)


def test_a_shortcut_edge_to_the_dominator_still_rolls_up() -> None:
    """A waits on C and B1, B1 waits only on C: every path from A reaches C."""
    blocked: dict[str, Row] = {"A": (["B1", "C"], []), "B1": (["C"], [])}
    assert immediate_dominators(blocked)["A"] == "C"
    assert collapse(blocked) == [("A_C_u", ["C"], [], ["A", "B1"])]


def test_the_cases_compose_to_a_fixed_point() -> None:
    """The diamond, the shortcut edge and a single blocker all land in one dominator tree."""
    blocked: dict[str, Row] = {
        "A": (["B1", "B2", "C"], []),
        "B1": (["C"], []),
        "B2": (["B1"], []),
        "D": (["A"], []),
    }
    got = collapse(blocked)
    assert [u[0] for u in got] == ["A_C_u"]
    assert got[0][3] == ["A", "B1"]
    where = paths(blocked, got)
    assert where["B1"] == "A_C_u/B1"
    assert immediate_dominators(blocked)["B2"] == "B1"
    assert immediate_dominators(blocked)["D"] == "A"


def test_waits_on_follows_blocked_on_edges_through_other_cards() -> None:
    """D waits on B which waits on C, so D waits on C; C does not wait on D."""
    blocked: dict[str, Row] = {"D": (["B"], []), "B": (["C"], []), "C": ([], [])}
    assert waits_on(blocked, "D", "C")
    assert not waits_on(blocked, "C", "D")


def test_only_an_enables_edge_the_target_does_not_wait_on_disagrees() -> None:
    """W1 enables W2 and W3; W3 waits on W1 (and on W9 too, a join), W2 waits on nothing."""
    blocked: dict[str, Row] = {
        "W1": ([], ["W2", "W3"]),
        "W2": ([], []),
        "W3": (["W1", "W9"], []),
    }
    assert disagreements(blocked) == [("W1", "W2")]
