# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W600: the burn-down tiers are declared data, read in order, one tier per repo."""

from nemik.rank import load_tiers as load
from nemik.tiers import ORDER, UNLISTED, rank


def test_the_declared_tiers_follow_the_operators_order() -> None:
    """Now before later before only-when-blocking before lowest; gabion is last, nemik first."""
    tiers = load()
    assert tiers["nemik"] == "now"
    assert tiers["paperkit"] == "later"
    assert tiers["amr-skills"] == "only-when-blocking"
    assert tiers["gabion"] == "lowest"
    assert rank(tiers["nemik"]) < rank(tiers["paperkit"]) < rank(tiers["gabion"])
    assert rank(UNLISTED) == len(ORDER)


def test_a_repo_in_two_tiers_keeps_the_more_urgent_and_an_absent_table_is_empty() -> (
    None
):
    """The earlier tier wins a duplicate; no [tiers] table means no tiers."""
    text = '[tiers]\nnow = ["a"]\nlater = ["a", "b"]\n'
    assert load(text) == {"a": "now", "b": "later"}
    assert load("x = 1\n") == {}
