# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2186: history turns its Diff and Churn records into JSON rows without dataclasses.asdict.

dataclasses.asdict is a Codon wall that history carried alone for 18 module-wall pairs, so diff_rows
and poll_rows write the field dicts out. These tests hold them to what asdict gives, after a JSON
round trip (asdict kept tuples where the rows now hold lists, which JSON cannot tell apart). A
field added to Diff or Churn and left out of its row changes asdict's answer, so the comparisons
below fail on it, even for the empty record.
"""

import json
from dataclasses import asdict

from nemik.history import Churn, Diff, diff_rows, poll_rows
from nemik.tomlview import table


def _json(value: object) -> object:
    """Round-trip a value through JSON, as the report does.

    Returns:
        The value as JSON would read it back.

    """
    loaded: object = json.loads(json.dumps(value))
    return loaded


def _diff() -> Diff:
    """Build a Diff with every field holding something.

    Returns:
        A populated Diff.

    """
    return Diff(
        minted=["W1", "W2"],
        closed=["W3"],
        dropped=["W4"],
        flips=[("W5", "ready", "done")],
        edges_added=[("waits", "W1", "W3")],
        edges_removed=[("enables", "W2", "W4")],
        new_cross_blocks=[("W1", "mtools:W9")],
    )


def test_a_diff_row_is_what_asdict_gave() -> None:
    """Give the same JSON as dataclasses.asdict for a Diff with every field set."""
    diff = _diff()
    expected: object = asdict(diff)
    assert _json(diff_rows({"nemik": diff})["nemik"]) == _json(expected)


def test_an_empty_diff_row_is_what_asdict_gave() -> None:
    """Give the same JSON as dataclasses.asdict for a Diff with nothing in it."""
    diff = Diff()
    expected: object = asdict(diff)
    assert _json(diff_rows({"a": diff})["a"]) == _json(expected)


def test_each_repo_keeps_its_own_row() -> None:
    """Key the rows by repo, one per Diff."""
    rows = diff_rows({"a": Diff(), "b": _diff()})
    assert sorted(rows) == ["a", "b"]


def test_a_poll_row_is_what_asdict_gave() -> None:
    """Give the same JSON as dataclasses.asdict for a Churn."""
    churn = Churn(step=30, polls=5, counts={"identical": 3, "attribute": 2})
    expected: object = asdict(churn)
    (row,) = poll_rows([churn])
    assert _json(row) == _json(expected)


def test_a_poll_row_does_not_share_the_counts_dict() -> None:
    """Copy the counts, as asdict did, so editing the row leaves the record alone."""
    churn = Churn(step=1, polls=1, counts={"identical": 1})
    (row,) = poll_rows([churn])
    assert table(row)["counts"] is not churn.counts
