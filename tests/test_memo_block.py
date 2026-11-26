# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1897: the memo block, a class now, answers, nests and unwinds as the decorator did."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from rdflib import Graph

from nemik import flow
from nemik.check import survey
from nemik.salience import audit, memo_audits

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from fractions import Fraction

FIXTURE = Path(__file__).parent / "fixtures" / "fleet"
ONCE = 1
TWICE = 2


class BoomError(Exception):
    """Raised inside a block, to see that the table is put back."""


def _graph_and_repo() -> tuple[Graph, str]:
    g = Graph()
    repos: list[str] = []
    for repo, qg, _ in survey(FIXTURE):
        repos.append(repo)
        if qg is not None:
            g += qg
    return g, repos[0]


def _counted(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"n": 0}
    real = flow.solve

    def counting(
        demand: Mapping[str, Fraction],
        needs: Mapping[str, Collection[str]],
        frontier: Collection[str],
        weights: Mapping[tuple[str, str], Fraction] | None = None,
        edge: Fraction = flow.ONE,
    ) -> flow.Flow:
        calls["n"] += 1
        return real(demand, needs, frontier, weights, edge)

    monkeypatch.setattr("nemik.salience.solve", counting)
    return calls


def test_inside_the_block_an_identical_audit_is_answered_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inside the block the second audit is a hit; outside it nothing is cached."""
    g, repo = _graph_and_repo()
    calls = _counted(monkeypatch)
    with memo_audits():
        audit(g, repo)
        audit(g, repo)
    assert calls["n"] == ONCE
    calls["n"] = 0
    audit(g, repo)
    audit(g, repo)
    assert calls["n"] == TWICE


def test_an_inner_block_leaves_the_outer_table_standing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MUTANT: an inner exit that cleared the table would solve the repo again."""
    g, repo = _graph_and_repo()
    calls = _counted(monkeypatch)
    with memo_audits():
        audit(g, repo)
        with memo_audits():
            audit(g, repo)
        audit(g, repo)
    assert calls["n"] == ONCE


def _audit_then_fail(g: Graph, repo: str) -> None:
    with memo_audits():
        audit(g, repo)
        raise BoomError


def test_a_block_left_by_an_exception_puts_the_table_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a raise inside the block, the next audit is not served from the dead table."""
    g, repo = _graph_and_repo()
    calls = _counted(monkeypatch)
    with pytest.raises(BoomError):
        _audit_then_fail(g, repo)
    calls["n"] = 0
    audit(g, repo)
    audit(g, repo)
    assert calls["n"] == TWICE
