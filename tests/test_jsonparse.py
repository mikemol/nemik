# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: the total arena parser agrees with json.loads on valid and malformed documents."""

import json
from pathlib import Path

import pytest

from nemik.jsonparse import Parser, parse

BS = chr(92)
NUMBERS = "[0,-0,0.5,-0.5,10,1e3,1E+3,2.5e-3]"
VALID = [
    '{"a":1,"b":[true,false,null],"c":{"d":"e"}}',
    "  [ 1 ,\t2 ,   3 ]  ",
    '{"k":"line' + BS + "nbreak" + BS + "ttab" + BS + BS + "slash" + BS + '"quote"}',
    '{"u":"' + BS + "u00e9" + BS + "u65e5" + BS + "ud83d" + BS + 'ude00"}',
    '"' + BS + '/ solidus"',
    '[[],{},[[]],{"x":{}}]',
    '{"neg":-5,"big":123456789012,"zero":0}',
    '""',
    '{"":""}',
    "true",
    "false",
    "null",
    "0",
    '"' + BS + 'ud800"',
    '"' + BS + 'udc00"',
    '"' + BS + 'ud83d"',
    '"' + BS + "ud83d" + BS + 'u0041"',
    '"' + BS + "u00E9" + BS + "uD83D" + BS + 'uDE00"',
    '{"a":{"a":{"a":{"a":{"a":{"a":1}}}}}}',
    "[" * 40 + "]" * 40,
]
MALFORMED = [
    "",
    " ",
    "{",
    "[",
    "[1,",
    "[1 2]",
    '{"a"}',
    '{"a":}',
    '{"a":1,}',
    "[1,]",
    "tru",
    "nul",
    "truex",
    '"abc',
    '"' + BS + 'x"',
    '"' + BS + 'u12"',
    '"' + BS + 'u12G4"',
    "01",
    "-",
    "1.",
    ".5",
    "1e",
    "+1",
    "[1] x",
    "{} {}",
    '{"a":1 "b":2}',
    "'single'",
    "[,1]",
    "{1:2}",
    '"tab\there"',
    '{"a":1}}',
    "[[[[",
    "[" * 40,
    "}",
    "]",
    ",",
    ":",
    '{"a":"b"',
    '["a",',
    "\x00",
    "1 2",
    "--1",
    "1.2.3",
]
DEVIATIONS = ["NaN", "Infinity", "-Infinity"]
SRC = Path(__file__).resolve().parents[1] / "src" / "nemik"


@pytest.mark.parametrize("doc", VALID)
def test_a_valid_document_parses_to_what_json_dumps_writes(doc: str) -> None:
    """The dump of a parsed valid document equals json.dumps of json.loads, compact."""
    loaded: object = json.loads(doc)
    assert parse(doc) == json.dumps(loaded, separators=(",", ":"))


def test_a_number_keeps_its_source_text() -> None:
    """The lexeme is kept verbatim, where json.dumps would rewrite -0 and 1e3."""
    loaded: object = json.loads(NUMBERS)
    assert parse(NUMBERS) == NUMBERS
    assert json.dumps(loaded, separators=(",", ":")) != NUMBERS


@pytest.mark.parametrize("doc", MALFORMED)
def test_a_malformed_document_is_an_error_where_json_loads_refuses_it(doc: str) -> None:
    """json.loads refuses every malformed document and the parser answers the word error."""
    with pytest.raises(ValueError, match=r".*"):
        json.loads(doc)
    assert parse(doc) == "error"


@pytest.mark.parametrize("doc", DEVIATIONS)
def test_nan_and_the_infinities_are_refused_unlike_json_loads(doc: str) -> None:
    """The parser is strict RFC 8259 and refuses what json.loads accepts as a Python extension."""
    json.loads(doc)
    assert parse(doc) == "error"


@pytest.mark.parametrize(
    ("doc", "at"),
    [("[1 2]", 3), ("[1,]", 3), ('{"a":1,}', 7), ("01", 1), ("tru", 0)],
)
def test_the_first_failure_position_is_recorded(doc: str, at: int) -> None:
    """The cursor stops at the first character the grammar refuses."""
    p = Parser(doc)
    p.value()
    p.skip()
    if p.ok and p.pos != len(doc):
        p.fail()
    assert not p.ok
    assert p.fail_at == at


def test_a_surrogate_pair_joins_into_one_astral_character() -> None:
    """The parsed string holds the astral character, not two surrogates (the dump hides that)."""
    p = Parser('"' + BS + "ud83d" + BS + 'ude00"')
    at = p.value()
    assert p.tree.nodes[at].text == chr(0x1F600)


def test_no_source_file_holds_a_literal_line_or_paragraph_separator() -> None:
    """The Write tool once turned an escape into U+2028, so the sources use chr() instead."""
    bad = [
        path.name
        for path in SRC.glob("*.py")
        if {chr(0x2028), chr(0x2029)} & set(path.read_text(encoding="utf-8"))
    ]
    assert bad == []
