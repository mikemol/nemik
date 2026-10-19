# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W711: nemik-collapse prints the umbrellas with their addresses and the escapes."""

from nemik.collapse import Row, lines

CHAIN: dict[str, Row] = {
    "a:W1": ([], ["a:W2", "a:W3"]),
    "a:W2": (["a:W1"], []),
    "a:W3": (["a:W1"], []),
}
ESCAPE: dict[str, Row] = {
    "a:W1": ([], ["a:W2"]),
    "a:W2": ([], []),
}


def test_two_cards_waiting_on_one_collapse_into_an_umbrella() -> None:
    """The umbrella is named, labelled, and its members listed with their n-path address."""
    out = lines(CHAIN)
    assert out[0].startswith("1 umbrella(s), 0 escape(s)")
    assert "2 cards collapse under a:W1" in out[1]
    assert any(line.strip().endswith("a:W2") for line in out[2:])
    assert any(line.strip().endswith("a:W3") for line in out[2:])


def test_an_enables_edge_whose_target_does_not_wait_is_an_escape() -> None:
    """The edge is named and no umbrella is made."""
    out = lines(ESCAPE)
    assert out[0].startswith("0 umbrella(s), 1 escape(s)")
    assert "escape: a:W1 enables a:W2, which does not wait on it" in out


def test_no_cards_print_only_the_header() -> None:
    """An empty fleet has nothing to report beyond the counts."""
    assert lines({}) == ["0 umbrella(s), 0 escape(s) over 0 open card(s)"]
