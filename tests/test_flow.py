"""nemik:W238: the laws of the conductance calculus, as the solver must satisfy them."""

from __future__ import annotations

from fractions import Fraction

import pytest

from nemik.flow import CycleError, series, solve

ONE = Fraction(1)
HALF = Fraction(1, 2)


def test_series_is_below_the_weakest_link_and_the_exact_half_life() -> None:
    assert series(ONE, ONE) == HALF
    assert series(Fraction(3), Fraction(1, 5)) < Fraction(1, 5)


def test_a_chain_is_below_its_weakest_link() -> None:
    flow = solve({"a": ONE}, {"a": ["b"], "b": ["f"]}, {"f"})
    assert flow.conductance["b"] == HALF
    assert flow.conductance["a"] == Fraction(1, 3)
    assert flow.conductance["a"] < min(ONE, flow.conductance["b"])


def test_parallel_prerequisites_add() -> None:
    flow = solve({"a": ONE}, {"a": ["f1", "f2"]}, {"f1", "f2"})
    assert flow.conductance["a"] == ONE


def test_a_prerequisite_named_twice_counts_once_but_two_sources_double() -> None:
    once = solve({"a": ONE}, {"a": ["f", "f"]}, {"f"})
    assert once.conductance["a"] == HALF
    twice = solve({"a": ONE}, {"a": ["f1", "f2"]}, {"f1", "f2"})
    assert twice.conductance["a"] == 2 * once.conductance["a"]


def test_demand_is_conserved_exactly() -> None:
    demand = {"d": Fraction(3), "x": Fraction(2, 7)}
    needs = {"d": ["a", "e"], "a": ["c"], "x": ["e"]}
    flow = solve(demand, needs, {"c", "e"})
    assert sum(flow.salience.values()) + sum(flow.stranded.values()) == sum(
        demand.values()
    )


def test_the_split_is_decided_by_the_physics_not_by_a_rule() -> None:
    # d needs a and e; a needs the ready c; e is ready. The longer branch carries less.
    flow = solve({"d": ONE}, {"d": ["a", "e"], "a": ["c"]}, {"c", "e"})
    assert flow.salience == {"c": Fraction(2, 5), "e": Fraction(3, 5)}
    assert flow.edges[("d", "a")] == Fraction(2, 5)


def test_a_landed_prerequisite_leaves_and_the_demand_goes_to_what_remains() -> None:
    flow = solve({"d": ONE}, {"d": ["e"]}, {"e"})
    assert flow.salience == {"e": ONE}


def test_demand_never_reaches_a_card_the_source_does_not_need() -> None:
    flow = solve({"a": ONE}, {"a": ["b"], "z": ["b"]}, {"b", "y"})
    assert set(flow.salience) == {"b"}


def test_demand_with_no_path_to_the_frontier_is_stranded_not_lost() -> None:
    flow = solve({"a": ONE}, {"a": ["outside"]}, {"f"})
    assert flow.salience == {}
    assert flow.stranded == {"a": ONE}


def test_a_cycle_is_reported_with_its_members() -> None:
    with pytest.raises(CycleError) as err:
        solve({"a": ONE}, {"a": ["b"], "b": ["a"]}, {"f"})
    assert err.value.members == ["a", "b"]


def test_the_answer_does_not_depend_on_input_order() -> None:
    needs = {"d": ["e", "a"], "a": ["c"], "x": ["a"]}
    flipped = {"x": ["a"], "a": ["c"], "d": ["a", "e"]}
    demand = {"d": ONE, "x": HALF}
    assert solve(demand, needs, {"e", "c"}) == solve(
        dict(reversed(demand.items())), flipped, {"c", "e"}
    )
