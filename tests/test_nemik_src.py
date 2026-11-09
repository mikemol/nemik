# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2087: bazel/nemik_src.bzl names exactly the tracked python files of src/nemik.

The operator ruled the glob away (host line 152589): inputs are named, with names from git ls-files.
A sandboxed test sees only the files BUILD names, so it cannot notice an unnamed one; the check is a
pure comparison that the commit hook feeds with `git ls-files`. These tests pin the comparison and
the generated text on fixtures, with no git.
"""

from pathlib import Path

from nemik_src import check, compare, named_in, render

from nemik.stackable import generated_files

ROOT = Path(__file__).resolve().parents[1]
TRACKED = ["src/nemik/__init__.py", "src/nemik/a.py", "src/nemik/core/x.py"]
FIRST = '    "src/nemik/__init__.py",'
SECOND = '    "src/nemik/a.py",'


def test_only_python_files_are_named() -> None:
    """Data, web assets and py.typed are not inputs of the wall incidence."""
    text = render([*TRACKED, "src/nemik/data/x.toml", "src/nemik/py.typed"])
    assert named_in(text) == set(TRACKED)


def test_rendered_names_round_trip_in_sorted_order() -> None:
    """What render writes, named_in reads back, whatever the order it was given."""
    assert named_in(render(list(reversed(TRACKED)))) == set(TRACKED)
    assert render(list(reversed(TRACKED))) == render(TRACKED)


def test_the_rendered_text_is_exactly_this() -> None:
    """The generated text is fixed: a header, one sorted name per line, a closing bracket."""
    lines = render(TRACKED).splitlines()
    assert lines[0].startswith('"""The python files of src/nemik')
    assert lines[-3:] == [SECOND, '    "src/nemik/core/x.py",', "]"]
    assert "NEMIK_PY = [" in lines
    assert lines.index(FIRST) < lines.index(SECOND)


def test_an_unnamed_tracked_file_is_missing() -> None:
    """A module added to the tree and not to the list is named missing."""
    text = render(TRACKED)
    added = [*TRACKED, "src/nemik/new.py"]
    assert compare(named_in(text), set(added)) == (["src/nemik/new.py"], [])
    problems = check(text, added)
    assert len(problems) == 1
    assert "src/nemik/new.py" in problems[0]


def test_a_named_file_that_is_not_tracked_is_extra() -> None:
    """A module removed from the tree and left in the list is named extra."""
    text = render([*TRACKED, "src/nemik/gone.py"])
    assert compare(named_in(text), set(TRACKED)) == ([], ["src/nemik/gone.py"])
    problems = check(text, TRACKED)
    assert len(problems) == 1
    assert "src/nemik/gone.py" in problems[0]


def test_a_stale_list_names_the_first_differing_line() -> None:
    """The message points at a line of the generated text, not only a name."""
    problems = check("NEMIK_PY = []\n", TRACKED)
    assert any("differs" in p for p in problems)


def test_the_list_is_registered_as_generated() -> None:
    """Listed in .claude/generated.json, a stack that regenerates it holds no lease on it."""
    text = (ROOT / ".claude" / "generated.json").read_text(encoding="utf-8")
    assert "bazel/nemik_src.bzl" in generated_files(text)
