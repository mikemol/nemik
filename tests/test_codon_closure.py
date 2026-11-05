# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1411: tools/codon_closure.py unions a module's Codon blockers over its import closure."""

from codon_closure import closure, own_row, report

LEAF = "import json\n\n\ndef f() -> int:\n    return 1\n"
CLI = "import argparse\n\nfrom nemik import leaf\n"
GRAPH = (
    "from datetime import UTC\n"
    "from typing import TYPE_CHECKING\n"
    "from rdflib import Graph\n"
    "from nemik.cli import main\n"
    "from nemik.leaf import f\n"
)
CLASSES = "from dataclasses import dataclass\n\n\n@dataclass(frozen=True)\nclass P:\n    x: int\n"


def test_a_pure_module_has_no_blocker_and_no_nemik_import() -> None:
    """Standard-library imports that Codon accepts add nothing."""
    assert own_row(LEAF) == (set(), set())


def test_blockers_and_nemik_imports_are_read_from_the_source() -> None:
    """Importing argparse is a blocker; a `from nemik...` import is an edge."""
    assert own_row(CLI) == ({"argparse"}, {"leaf"})
    blockers, deps = own_row(GRAPH)
    assert blockers == {"datetime.UTC", "typing.TYPE_CHECKING", "rdflib"}
    assert deps == {"cli", "leaf"}


def test_a_dataclass_is_a_blocker_by_its_decorator() -> None:
    """The decorator call is read, not only the import."""
    assert "@dataclass" in own_row(CLASSES)[0]


def test_the_closure_unions_blockers_through_the_import_graph() -> None:
    """A module inherits every blocker of the modules it reaches, and a cycle ends."""
    rows = {
        "leaf": own_row(LEAF),
        "cli": own_row(CLI),
        "top": own_row(GRAPH),
        "loop": ({"hashlib"}, {"loop"}),
    }
    assert closure(rows, "leaf") == set()
    assert closure(rows, "cli") == {"argparse"}
    assert closure(rows, "top") == {
        "argparse",
        "datetime.UTC",
        "rdflib",
        "typing.TYPE_CHECKING",
    }
    assert closure(rows, "loop") == {"hashlib"}


def test_the_report_lists_the_fewest_blockers_first() -> None:
    """Rows sort by blocker count, then name, each with its kinds."""
    rows = {"leaf": own_row(LEAF), "cli": own_row(CLI), "top": own_row(GRAPH)}
    lines = report(rows, ["top", "cli", "leaf"])
    assert lines[0] == "0 leaf: "
    assert lines[1] == "1 cli: argparse"
    assert lines[2].startswith("4 top: argparse, datetime.UTC")
