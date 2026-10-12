"""nemik:W401: a solve is answered from the cache when nothing inside its sources' cones changed."""

from __future__ import annotations

from fractions import Fraction

from nemik import flow


def _counting(monkeypatch) -> dict[str, int]:
    calls = {"n": 0}
    real = flow._solve

    def counted(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(flow, "_solve", counted)
    monkeypatch.setattr(flow, "_SOLVES", flow.OrderedDict())
    return calls


def test_a_change_outside_the_cones_is_answered_from_the_cache(monkeypatch) -> None:
    calls = _counting(monkeypatch)
    demand = {"x": Fraction(1)}
    needs = {"x": ["a", "b"], "y": ["c"]}  # y's cone is outside x's
    first = flow.solve(demand, needs, {"a", "b", "c"})
    # y now needs d too: nothing x's cone holds has changed
    second = flow.solve(
        demand, {"x": ["a", "b"], "y": ["c", "d"]}, {"a", "b", "c", "d"}
    )
    assert calls["n"] == 1
    assert second == first


def test_a_change_inside_a_cone_is_solved_again(monkeypatch) -> None:
    calls = _counting(monkeypatch)
    demand = {"x": Fraction(1)}
    first = flow.solve(demand, {"x": ["a", "b"]}, {"a", "b"})
    second = flow.solve(demand, {"x": ["a", "b", "c"]}, {"a", "b", "c"})
    assert calls["n"] == 2
    assert first.salience != second.salience
