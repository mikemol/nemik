# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1678: tools/atomize_walls.py turns a blocker closure into wall cards and row cards."""

from atomize_walls import (
    minted,
    needs_of,
    parse_queue,
    plan,
    row_title,
    sites_of,
    size_of,
    wall_title,
)
from codon_closure import Row, own_row

ROWS: dict[str, Row] = {
    "leaf": own_row("import json\n"),
    "cli": own_row("import argparse\nfrom nemik import leaf\n"),
    "data": own_row(
        "from dataclasses import dataclass\n\n\n@dataclass(frozen=True)\nclass P:\n    x: int\n"
    ),
    "top": own_row(
        "import argparse\nfrom nemik import data\nfrom nemik.cli import main\n"
    ),
}
LISTED = ["cli", "data", "top"]


def test_the_decorator_and_the_import_of_dataclasses_are_one_wall() -> None:
    """A module carrying both is listed once under one kind, and sites repeat no module."""
    assert sites_of(ROWS)["dataclass"] == ["data"]
    assert sites_of(ROWS)["argparse"] == ["cli", "top"]


def test_a_row_needs_the_walls_of_its_whole_closure() -> None:
    """`top` reaches dataclass through `data` and argparse through itself and `cli`."""
    assert needs_of(ROWS, LISTED) == {
        "cli": ["argparse"],
        "data": ["dataclass"],
        "top": ["argparse", "dataclass"],
    }


def test_the_plan_has_one_wall_per_kind_and_one_row_per_module() -> None:
    """Walls carry the modules that use the kind as manifest and wait on nothing."""
    walls, rows = plan(ROWS, LISTED)
    assert [w.title for w in walls] == [
        wall_title("argparse"),
        wall_title("dataclass"),
    ]
    assert walls[0].manifest == ("src/nemik/cli.py", "src/nemik/top.py")
    assert walls[0].size == "small"
    assert all(w.waits_on == () for w in walls)
    assert [r.title for r in rows] == [row_title(n) for n in LISTED]
    assert rows[2].waits_on == ("argparse", "dataclass")


def test_the_sizes_follow_the_number_of_modules() -> None:
    """Up to 3 modules is small, up to 12 medium, more is large."""
    assert [size_of(n) for n in (1, 3, 4, 12, 13)] == [
        "small",
        "small",
        "medium",
        "medium",
        "large",
    ]


def test_a_card_is_found_again_by_its_exact_title() -> None:
    """The queue listing is read into {title: symbol}, so a second run reuses the card."""
    listing = (
        f" 1. W7 ready    {wall_title('argparse')}  — enables W9\n"
        f" 2. W8 blocked  {row_title('cli')}\n"
        "not a card line\n"
    )
    assert parse_queue(listing) == {
        wall_title("argparse"): "W7",
        row_title("cli"): "W8",
    }


def test_the_writer_answer_is_read_for_the_new_symbol() -> None:
    """`W12 added; ...` gives W12; anything else gives nothing."""
    assert minted("W12 added; state_hash=v2:abc\n") == "W12"
    assert not minted("REFUSED: nope")
