# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W593: nemik.flow.solve gives the answers nemik pins for each case of flow_cases."""

from fractions import Fraction

import pytest
from flow_cases import (
    CASES,
    CONDUCTANCE,
    FIBRE,
    SALIENCE,
    SALIENCE_KEYS,
    STRANDED,
    Case,
)

from nemik.flow import Flow, solve


def _solve(case: Case) -> Flow:
    """Run nemik's solver on one corpus case.

    Args:
        case: A (name, prereq, ready, demand) tuple.

    Returns:
        The flow.

    """
    _, prereq, ready, demand = case
    needs = {node: [name for name, _ in edges] for node, edges in prereq.items()}
    weights = {
        (node, name): weight for node, edges in prereq.items() for name, weight in edges
    }
    return solve(demand, needs, ready, weights)


def test_case_names_are_unique() -> None:
    """The corpus keys its tables by name."""
    names = [case[0] for case in CASES]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("case", CASES, ids=[case[0] for case in CASES])
def test_the_solver_gives_the_pinned_answer(case: Case) -> None:
    """Salience, stranded demand, fibre and conductance, wherever the case pins them."""
    name = case[0]
    flow = _solve(case)
    if name in SALIENCE:
        assert flow.salience == SALIENCE[name]
    if name in STRANDED:
        assert flow.stranded == STRANDED[name]
    if name in FIBRE:
        assert flow.fibre["f"] == FIBRE[name]
    if name in CONDUCTANCE:
        assert 1 / flow.potential["a"] == CONDUCTANCE[name]
    if name in SALIENCE_KEYS:
        assert set(flow.salience) == SALIENCE_KEYS[name]


def test_a_chain_is_below_its_weakest_link() -> None:
    """The weighted chain's conductance 3/16 is below its weakest edge, 1/5."""
    weighted = next(case for case in CASES if case[0] == "chain weighted")
    assert 1 / _solve(weighted).potential["a"] < Fraction(1, 5)


def test_two_sources_double_what_one_named_twice_gives() -> None:
    """A prerequisite named twice counts once; two distinct sources double it."""
    assert CONDUCTANCE["parallel"] == 2 * CONDUCTANCE["named twice"]
