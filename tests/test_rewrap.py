# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1225: tools/rewrap.py splits long comment and docstring lines and nothing else."""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
WIDTH = 40
SENTENCE = "one two three four five six seven eight nine ten eleven twelve"


def _tool() -> ModuleType:
    # tools/ is not a package: load the file as a script would run it
    path = ROOT / "tools" / "rewrap.py"
    spec = importlib.util.spec_from_file_location("rewrap", path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rewrap(source: str) -> str:
    return cast("str", _tool().rewrap(source, WIDTH))


def test_a_long_comment_is_split_with_the_same_indent_and_words() -> None:
    """The words and their order survive; each line fits and keeps the hash."""
    source = f"def f():\n    # {SENTENCE}\n    return 1\n"
    rows = _rewrap(source).split("\n")
    assert all(len(row) <= WIDTH for row in rows)
    comment = [row for row in rows if row.lstrip().startswith("#")]
    assert len(comment) > 1
    assert all(row.startswith("    # ") for row in comment)
    words = " ".join(row.lstrip("# ").strip() for row in comment).split()
    assert words == SENTENCE.split()


def test_a_docstring_body_line_is_split_but_its_first_line_is_not() -> None:
    """Splitting a summary would make D205 fire, so the first line stays as it is."""
    first = "A summary line that is far longer than forty columns."
    body = "a body line that is also far longer than forty columns wide"
    source = f'"""{first}\n\n{body}\n"""\n'
    rows = _rewrap(source).split("\n")
    assert rows[0] == f'"""{first}'
    assert len(rows) > len(source.split("\n"))
    assert " ".join(rows[2:-2]).split() == body.split()


def test_directives_one_word_comments_and_short_lines_are_left_alone() -> None:
    """A directive comment, a long URL with no space and a short line do not change."""
    url = "https://example.com/a/very/long/url/with/no/space/in/it/at/all/so/it/stays"
    source = (
        "x = 1  # a trailing comment on a code line that is longer than forty columns\n"
        "# fmt: this directive comment is longer than forty columns, so it stays\n"
        f"# {url}\n"
        "# short\n"
    )
    assert _rewrap(source) == source


def test_the_output_parses_and_a_second_pass_changes_nothing() -> None:
    """A rewrap is valid Python, and rewrapping its own output is a no-op."""
    source = f"# {SENTENCE} {SENTENCE}\nx = 1\n"
    once = _rewrap(source)
    compile(once, "once", "exec")
    assert _rewrap(once) == once
