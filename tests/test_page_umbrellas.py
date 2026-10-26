# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W975: the page carries the published umbrella rows when it combines its sources."""

from webpage import evaluated

TWO_SOURCES = """combine([
  {nodes: [], edges: [], umbrellas: [{id: "u", card: "a"}]},
  {nodes: [], edges: [], umbrellas: [{id: "u", card: "a"}, {id: "u", card: "b"}]},
]).umbrellas.length"""
ONE_SOURCE_WITHOUT = "combine([{nodes: [], edges: []}]).umbrellas.length"
DISTINCT_ROWS = 2


def test_a_row_two_sources_both_publish_is_kept_once() -> None:
    """Rows join by umbrella and member, like cards and edges join by identity."""
    assert evaluated(TWO_SOURCES) == DISTINCT_ROWS


def test_a_source_without_umbrellas_adds_none() -> None:
    """A source that publishes no umbrellas.json contributes an empty list, not a failure."""
    assert evaluated(ONE_SOURCE_WITHOUT) == 0
