# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1225: tools/liftdoc.py moves an opening comment into a docstring."""

import ast
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
WIDTH = 60
FIRST = "nemik:W1: the first."
MORE = "Then more words follow it here."
ONE = "nemik:W1: a thing happens when the input is empty."


def _tool() -> ModuleType:
    # tools/ is not a package: load the file as a script would run it
    path = ROOT / "tools" / "liftdoc.py"
    spec = importlib.util.spec_from_file_location("liftdoc", path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lift(source: str) -> str:
    return cast("str", _tool().lift(source, WIDTH))


def _doc(source: str, name: str) -> str | None:
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_docstring(node)
    return None


def _function(name: str, comment: list[str]) -> str:
    rows = "".join(f"    # {line}\n" for line in comment)
    return f"def {name}() -> None:\n{rows}    return None\n"


def test_a_one_sentence_comment_becomes_a_one_line_docstring_and_leaves() -> None:
    """The comment is moved, not copied, and the function's code is unchanged."""
    out = _lift(_function("test_a", [ONE]))
    assert _doc(out, "test_a") == ONE
    assert "#" not in out
    assert out.count("return None") == 1


def test_a_second_sentence_follows_a_blank_line_as_a_paragraph() -> None:
    """The summary is the first sentence, so ruff's D205 has nothing to say."""
    out = _lift(_function("test_a", [f"{FIRST} {MORE}"]))
    assert _doc(out, "test_a") == f"{FIRST}\n\n{MORE}"
    assert f'"""{FIRST}\n\n' in out


def test_what_ruff_would_refuse_is_left_as_a_comment() -> None:
    """A directive, no period, an over-long first sentence, a lowercase word, a diagram."""
    long = "nemik:W1: " + "word " * 20 + "ends here."
    cases = [
        ["noqa: this stays where it is."],
        ["nemik:W1: no sentence end here"],
        [long],
        ["lowercase first word stays."],
        ["nemik:W1: a <- b <- c is a diagram."],
    ]
    for comment in cases:
        source = _function("test_a", comment)
        assert _lift(source) == source, comment


def test_a_function_that_is_not_a_test_needs_a_tag_not_a_plain_word() -> None:
    """Ruff's D401 skips test names only, so a plain first word would have to be a verb."""
    plain = _function("helper", ["Does a thing when asked."])
    tagged = _function("helper", ["nemik:W2: does a thing when asked."])
    assert _lift(plain) == plain
    assert _doc(_lift(tagged), "helper") == "nemik:W2: does a thing when asked."


def test_documented_and_private_functions_are_untouched() -> None:
    """Only a public function with no docstring is a candidate."""
    documented = (
        'def test_a() -> None:\n    """Already said."""\n'
        "    # nemik:W1: ignored.\n    return None\n"
    )
    private = _function("_helper", ["nemik:W1: not public."])
    assert _lift(documented) == documented
    assert _lift(private) == private


def test_the_output_parses_and_a_second_pass_changes_nothing() -> None:
    """A lift is valid Python and rewriting its own output is a no-op."""
    once = _lift(_function("test_a", [f"{FIRST} And the second one, and the third."]))
    compile(once, "once", "exec")
    assert _lift(once) == once
