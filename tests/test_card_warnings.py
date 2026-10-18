# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W687: every Warning nemik-check emits for a card is in that card's UI payload."""

import inspect
from pathlib import Path
from typing import cast

from rdflib import Graph

from nemik import serve
from nemik.adapter import BASE, bind
from nemik.blocks import node_flags, warnings_by_card
from nemik.check import survey

FLEET = Path(__file__).parent / "fixtures" / "fleet"
SHOWN = ("Warning", "Violation")


def _warnings(flags: dict[str, object]) -> list[tuple[str, str]]:
    """Read the (severity, message) pairs out of a node's flags.

    Args:
        flags: What node_flags holds for one node.

    Returns:
        The pairs in order; empty when the node has no warnings.

    """
    held = cast("list[dict[str, str]]", flags.get("warnings", []))
    return [(w["severity"], w["message"]) for w in held]


def test_grouping_keeps_warnings_and_violations_in_order() -> None:
    """Info rows and repo-level `--` rows are no card's; the rest keep their order."""
    rows = {
        "alpha": [
            ("Warning", "W1", "first"),
            ("Info", "W1", "not shown"),
            ("Violation", "W1", "second"),
            ("Warning", "--", "belongs to the repo"),
            ("Warning", "W2", "other card"),
        ]
    }
    got = warnings_by_card(rows)
    assert got[f"{BASE}alpha/W1"] == {
        "warnings": [
            {"severity": "Warning", "message": "first"},
            {"severity": "Violation", "message": "second"},
        ]
    }
    assert list(got) == [f"{BASE}alpha/W1", f"{BASE}alpha/W2"]


def test_every_cli_warning_for_a_card_is_in_the_flags_serve_puts_on_its_node() -> None:
    """Over the fleet fixture: the survey's rows and the node flags agree, row for row.

    The CLI prints the survey's rows and the payload takes the same rows through node_flags, so a
    new shape reaches the view with no extra work, and this fails if the two stop agreeing.
    """
    rows: dict[str, list[tuple[str, str, str]]] = {}
    whole = bind(Graph())
    for repo, g, findings in survey(FLEET):
        rows[repo] = findings
        if g is not None:
            whole += g
    expected = {
        (f"{BASE}{repo}/{symbol}", severity, message)
        for repo, found in rows.items()
        for severity, symbol, message in found
        if severity in SHOWN and symbol != "--"
    }
    assert expected, "the fixture fleet emits no card-level Warning to compare"
    carried = {
        (card, severity, message)
        for card, flags in node_flags(whole, rows).items()
        for severity, message in _warnings(flags)
    }
    assert carried == expected


def test_serve_fills_each_node_from_node_flags() -> None:
    """The payload builder takes its per-node extras from node_flags and nothing else."""
    assert "node_flags(g, findings)" in inspect.getsource(serve)
