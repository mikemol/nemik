# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1994: tools/ratchet_atomizer.py plans a leaf per debt row and an umbrella per ratchet."""

from ratchet_atomizer import TITLE_LIMIT, Row, leaf_title, plan, umbrella_title

ROWS = [
    Row("hooks/pyproject.toml", "src/a.py", "src/a.py", "E501"),
    Row("hooks/pyproject.toml", "src/a.py", "src/a.py", "D103"),
    Row("hooks/pyproject.toml", "src/b.py", "src/b.py", "E501"),
    Row("codon-baseline.json", "ask_cli", "src/nemik/ask_cli.py", ""),
]


def test_a_leaf_per_row_and_an_umbrella_per_ratchet() -> None:
    """Four rows are four leaves and two umbrellas, each umbrella waiting on its own leaves."""
    specs = plan(ROWS)
    titles = [s.title for s in specs]
    assert len(specs) == len(ROWS) + 2
    assert titles[-2:] == [
        umbrella_title("codon-baseline.json"),
        umbrella_title("hooks/pyproject.toml"),
    ]
    hooks = next(s for s in specs if s.title == umbrella_title("hooks/pyproject.toml"))
    assert hooks.waits_on == tuple(leaf_title(r) for r in ROWS[:3])
    assert all(not s.waits_on for s in specs[: len(ROWS)])


def test_a_title_depends_on_the_row_alone_so_a_second_run_finds_the_card() -> None:
    """The same rows plan to the same titles, in any row order for the leaves' set."""
    again = plan(list(reversed(ROWS)))
    assert {s.title for s in plan(ROWS)} == {s.title for s in again}
    assert leaf_title(ROWS[0]) != leaf_title(ROWS[1])


def test_an_unknown_row_and_a_repeated_row_are_planned_once_or_not_at_all() -> None:
    """MUTANT: planning the unknown row or a duplicate would add a card the census lacks."""
    rows = [*ROWS, Row("x", "unknown", "", ""), ROWS[0]]
    assert len(plan(rows)) == len(plan(ROWS))


def test_a_title_stays_within_the_writers_limit() -> None:
    """A long key is cut, so the writer does not refuse the title."""
    long = Row("r", "k" * 400, "f", "E501")
    assert len(leaf_title(long)) <= TITLE_LIMIT
