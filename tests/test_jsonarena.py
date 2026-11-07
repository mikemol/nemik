# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: the arena tree writes the same compact JSON as json.dumps."""

import json

import pytest

from nemik.jsonarena import Tree, Val, escape, escape_char

LINE_SEPARATOR = chr(0x2028)
PARAGRAPH_SEPARATOR = chr(0x2029)
ACCENT = chr(0xE9)
TRICKY = [
    "",
    "plain",
    'quo"te',
    "back\\slash",
    "line\nbreak\ttab\rreturn",
    "\x00\x01\x1f",
    "\x08\x0c",
    "del\x7f",
    "caf" + ACCENT,
    chr(0x65E5) + chr(0x672C),
    LINE_SEPARATOR + PARAGRAPH_SEPARATOR,
    "emoji " + chr(0x1F600),
    chr(0xD800),
]


@pytest.mark.parametrize("text", TRICKY)
def test_a_string_escapes_as_json_dumps_does(text: str) -> None:
    """The escaped inside of a string equals json.dumps' without its quotes."""
    assert escape(text) == json.dumps(text)[1:-1]


def test_a_character_escapes_alone_as_it_does_in_a_string() -> None:
    """escape_char over a text equals escape of it."""
    assert "".join(escape_char(c) for c in TRICKY[8]) == escape(TRICKY[8])


def test_a_nested_value_dumps_as_json_dumps_does() -> None:
    """Objects keep their key order, arrays their element order, booleans and strings their text."""
    t = Tree()
    inner = t.array([t.string("a"), t.true(), t.false()])
    root = t.obj(["z", "a", ACCENT], [inner, t.string("v"), t.obj([], [])])
    want = {"z": ["a", True, False], "a": "v", ACCENT: {}}
    assert t.dump(root) == json.dumps(want, separators=(",", ":"))


def test_an_empty_array_and_object_dump_as_brackets() -> None:
    """Empty containers are written without a stray comma."""
    t = Tree()
    assert t.dump(t.array([])) == "[]"
    assert t.dump(t.obj([], [])) == "{}"


def test_a_number_keeps_its_source_text() -> None:
    """A number node dumps its text, so 1e3 stays 1e3 where json.dumps would write 1000.0."""
    t = Tree()
    node = Val("number")
    node.text = "1e3"
    assert t.dump(t.add(node)) == "1e3"
