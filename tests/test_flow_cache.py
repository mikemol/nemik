# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W401: a solve is answered from the cache when nothing inside its sources' cones changed."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

from nemik import flow

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pytest


def _counting(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"n": 0}
    real = flow._solve

    def counted(
        demand: Mapping[str, Fraction],
        front: set[str],
        prereq: dict[str, list[str]],
        weights: Mapping[tuple[str, str], Fraction] | None,
        edge: Fraction,
    ) -> flow.Flow:
        calls["n"] += 1
        return real(demand, front, prereq, weights, edge)

    monkeypatch.setattr(flow, "_solve", counted)
    monkeypatch.setattr(flow, "_SOLVES", flow.OrderedDict())
    return calls


def test_a_change_outside_the_cones_is_answered_from_the_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_a_change_inside_a_cone_is_solved_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _counting(monkeypatch)
    demand = {"x": Fraction(1)}
    first = flow.solve(demand, {"x": ["a", "b"]}, {"a", "b"})
    second = flow.solve(demand, {"x": ["a", "b", "c"]}, {"a", "b", "c"})
    assert calls["n"] == 2
    assert first.salience != second.salience
