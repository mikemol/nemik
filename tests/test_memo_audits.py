# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W403: a document build answers identical flow solves once; the document is unchanged."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from rdflib import Graph

from nemik import flow
from nemik.check import survey
from nemik.serve import _to_json, to_json

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from fractions import Fraction

    import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "fleet"


def _graph() -> tuple[Graph, dict]:
    g, findings = Graph(), {}
    for repo, qg, fs in survey(FIXTURE):
        findings[repo] = fs
        if qg is not None:
            g += qg
    return g, findings


def test_the_memo_changes_no_number_and_cuts_the_solves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The memo changes no number and cuts the solves."""
    g, findings = _graph()
    calls = {"n": 0}
    real = flow.solve

    def counted(
        demand: Mapping[str, Fraction],
        needs: Mapping[str, Collection[str]],
        frontier: Collection[str],
        weights: Mapping[tuple[str, str], Fraction] | None = None,
        edge: Fraction = flow.ONE,
    ) -> flow.Flow:
        calls["n"] += 1
        return real(demand, needs, frontier, weights, edge)

    monkeypatch.setattr("nemik.salience.solve", counted)
    plain = _to_json(g, findings)
    unmemoized = calls["n"]
    calls["n"] = 0
    memoized = to_json(g, findings)
    assert json.dumps(memoized, sort_keys=True) == json.dumps(plain, sort_keys=True)
    assert unmemoized > 0
    assert calls["n"] < unmemoized, (calls["n"], unmemoized)
