# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1994: tools/ratchet_atomizer.py plans a leaf per key and an umbrella per ratchet."""

from ratchet_atomizer import TITLE_LIMIT, Row, leaf_title, plan, umbrella_title

ROWS = [
    Row("hooks/pyproject.toml", "src/a.py", "src/a.py", "E501"),
    Row("hooks/pyproject.toml", "src/a.py", "src/a.py", "D103"),
    Row("hooks/pyproject.toml", "src/b.py", "src/b.py", "E501"),
    Row("codon-baseline.json", "ask_cli", "src/nemik/ask_cli.py", "as_written"),
    Row("codon-baseline.json", "ask_cli", "src/nemik/ask_cli.py", "stripped"),
]
LEAVES = 3
UMBRELLAS = 2


def test_a_leaf_per_key_and_an_umbrella_per_ratchet() -> None:
    """Five rows of three keys are three leaves and two umbrellas, each waiting on its leaves."""
    specs = plan(ROWS)
    titles = [s.title for s in specs]
    assert len(specs) == LEAVES + UMBRELLAS
    assert titles[-2:] == [
        umbrella_title("codon-baseline.json"),
        umbrella_title("hooks/pyproject.toml"),
    ]
    hooks = next(s for s in specs if s.title == umbrella_title("hooks/pyproject.toml"))
    assert hooks.waits_on == (
        leaf_title("hooks/pyproject.toml", "src/a.py", ("D103", "E501")),
        leaf_title("hooks/pyproject.toml", "src/b.py", ("E501",)),
    )
    assert all(not s.waits_on for s in specs[:LEAVES])


def test_the_rules_of_a_key_are_listed_in_its_leaf_sorted() -> None:
    """MUTANT: one leaf per entry would plan two cards for src/a.py and two for ask_cli."""
    titles = [s.title for s in plan(ROWS)]
    assert (
        "Ratchet hooks/pyproject.toml: remove the entries of src/a.py (D103, E501)"
        in titles
    )
    assert (
        "Ratchet codon-baseline.json: remove the entries of ask_cli (as_written, stripped)"
        in titles
    )
    assert sum("src/a.py" in t for t in titles) == 1


def test_a_leaf_carries_the_keys_file_as_its_manifest() -> None:
    """The two modes of one module share one manifest file, so they are one leaf."""
    spec = next(s for s in plan(ROWS) if "ask_cli" in s.title and not s.waits_on)
    assert spec.manifest == ("src/nemik/ask_cli.py",)


def test_a_title_depends_on_the_key_and_its_rules_alone() -> None:
    """The same rows plan to the same titles, in any row order for the leaves' set."""
    again = plan(list(reversed(ROWS)))
    assert {s.title for s in plan(ROWS)} == {s.title for s in again}
    assert leaf_title("r", "k", ("A",)) != leaf_title("r", "k", ("A", "B"))


def test_an_unknown_row_and_a_repeated_row_are_planned_once_or_not_at_all() -> None:
    """MUTANT: planning the unknown row or a duplicate would add a card the census lacks."""
    rows = [*ROWS, Row("x", "unknown", "", ""), ROWS[0]]
    assert len(plan(rows)) == len(plan(ROWS))


def test_a_title_stays_within_the_writers_limit() -> None:
    """A long key is cut, so the writer does not refuse the title."""
    assert len(leaf_title("r", "k" * 400, ("E501",))) <= TITLE_LIMIT
