"""nemik:W238: the laws of the conductance calculus and gcalculus's controls (gcalculus:W208)."""

from __future__ import annotations

from fractions import Fraction

from nemik.flow import solve

ONE = Fraction(1)
HALF = Fraction(1, 2)


def test_a_chain_composes_in_series_and_is_below_its_weakest_link() -> None:
    unit = solve({"a": ONE}, {"a": ["b"], "b": ["f"]}, {"f"})
    assert unit.potential["a"] == 2  # resistance 2 = conductance 1/2 = AND(1, 1)
    weighted = {("a", "b"): Fraction(3), ("b", "f"): Fraction(1, 5)}
    flow = solve({"a": ONE}, {"a": ["b"], "b": ["f"]}, {"f"}, weighted)
    conductance = 1 / flow.potential["a"]
    assert conductance == Fraction(3, 16)
    assert conductance < Fraction(1, 5)


def test_parallel_prerequisites_add() -> None:
    flow = solve({"a": ONE}, {"a": ["f1", "f2"]}, {"f1", "f2"})
    assert 1 / flow.potential["a"] == 2  # OR(1, 1) = 2


def test_a_prerequisite_named_twice_counts_once_but_two_sources_double() -> None:
    once = solve({"a": ONE}, {"a": ["f", "f"]}, {"f"})
    twice = solve({"a": ONE}, {"a": ["f1", "f2"]}, {"f1", "f2"})
    assert 1 / twice.potential["a"] == 2 * (1 / once.potential["a"])


def test_demand_is_conserved_exactly_over_many_sources() -> None:
    demand = {"d": Fraction(3), "x": Fraction(2, 7), "a": HALF}
    needs = {"d": ["a", "e"], "a": ["c"], "x": ["e", "a"]}
    flow = solve(demand, needs, {"c", "e"})
    assert sum(flow.salience.values()) + sum(flow.stranded.values()) == sum(
        demand.values()
    )


def test_a_card_the_source_does_not_need_gets_nothing() -> None:
    # a needs b; d needs a and e. Demand at a reaches b only: a global solve leaks 1/3 to e.
    flow = solve({"a": ONE}, {"a": ["b"], "d": ["a", "e"]}, {"b", "e"})
    assert flow.salience == {"b": ONE}


def test_fill_in_through_a_shared_prerequisite_does_not_leak_either() -> None:
    # z needs y1 needs s needs r; y2 needs s and q. Eliminating s globally would feed q.
    needs = {"z": ["y1"], "y1": ["s"], "s": ["r"], "y2": ["s", "q"]}
    flow = solve({"z": ONE}, needs, {"r", "q"})
    assert flow.salience == {"r": ONE}


def test_reconvergence_counts_the_shared_prerequisite_once() -> None:
    # x needs y1 and y2; both need s; s needs r3; y1 needs r1; y2 needs r2. A series-parallel
    # fold gives each ready card 1/3; the nodal solve gives 3/8, 3/8 and 1/4.
    needs = {"x": ["y1", "y2"], "y1": ["s", "r1"], "y2": ["s", "r2"], "s": ["r3"]}
    flow = solve({"x": ONE}, needs, {"r1", "r2", "r3"})
    assert flow.salience == {
        "r1": Fraction(3, 8),
        "r2": Fraction(3, 8),
        "r3": Fraction(1, 4),
    }


def test_a_landed_prerequisite_leaves_and_the_demand_goes_to_what_remains() -> None:
    both = solve({"d": ONE}, {"d": ["a", "e"], "a": ["c"]}, {"c", "e"})
    assert set(both.salience) == {"c", "e"}
    landed = solve({"d": ONE}, {"d": ["e"]}, {"e"})
    assert landed.salience == {"e": ONE}


def test_demand_whose_cone_has_no_ready_card_is_stranded_not_lost() -> None:
    flow = solve({"a": ONE}, {"a": ["outside"]}, {"f"})
    assert flow.salience == {}
    assert flow.stranded == {"a": ONE}


def test_a_cycle_inside_a_cone_is_solved() -> None:
    flow = solve({"b": ONE}, {"a": ["b", "f"], "b": ["a"]}, {"f"})
    assert flow.salience == {"f": ONE}


def test_a_source_that_is_ready_is_absorbed_where_it_stands() -> None:
    flow = solve({"f": HALF}, {}, {"f"})
    assert flow.salience == {"f": HALF}


def test_the_fibre_keeps_the_part_each_source_contributed() -> None:
    flow = solve({"p": ONE, "q": ONE}, {"p": ["f"], "q": ["f"]}, {"f"})
    assert flow.salience == {"f": 2 * ONE}
    assert flow.fibre["f"] == {"p": ONE, "q": ONE}


def test_the_answer_does_not_depend_on_input_order() -> None:
    needs = {"d": ["e", "a"], "a": ["c"], "x": ["a"]}
    flipped = {"x": ["a"], "a": ["c"], "d": ["a", "e"]}
    demand = {"d": ONE, "x": HALF}
    assert solve(demand, needs, {"e", "c"}) == solve(
        dict(reversed(demand.items())), flipped, {"c", "e"}
    )
