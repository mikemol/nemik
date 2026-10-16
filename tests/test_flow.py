# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W238: the laws of the conductance calculus that no single case can state.

The cases (chain, parallel, reconvergence, stranded, cycle, fibre and the rest) live as data in
tests/flow_cases.py, in gcalculus's flow_corpus shape, and tests/test_flow_corpus.py pins their
answers (nemik:W593); what stays here are the properties over many inputs.
"""

from __future__ import annotations

from fractions import Fraction

from nemik.flow import solve

ONE = Fraction(1)
HALF = Fraction(1, 2)


def test_demand_is_conserved_exactly_over_many_sources() -> None:
    demand = {"d": Fraction(3), "x": Fraction(2, 7), "a": HALF}
    needs = {"d": ["a", "e"], "a": ["c"], "x": ["e", "a"]}
    flow = solve(demand, needs, {"c", "e"})
    assert sum(flow.salience.values()) + sum(flow.stranded.values()) == sum(
        demand.values()
    )


def test_the_answer_does_not_depend_on_input_order() -> None:
    needs = {"d": ["e", "a"], "a": ["c"], "x": ["a"]}
    flipped = {"x": ["a"], "a": ["c"], "d": ["a", "e"]}
    demand = {"d": ONE, "x": HALF}
    assert solve(demand, needs, {"e", "c"}) == solve(
        dict(reversed(demand.items())), flipped, {"c", "e"}
    )
