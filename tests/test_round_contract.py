# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1033: nemik's round file meets what its two other parties read, on one recorded file.

luthen's egress gate rules the file line by line (the head must be exactly {"as_of"}, every other
line a card with a repo) and mtools' round_check reads the first as_of stamp and, per card, repo,
symbol and an integer-parsable rank. The recorded file is what the writer must reproduce byte for
byte, and what each party's rule is checked against here; luthen and mtools check their parsers
against the same bytes in their own trees.
"""

import re
from pathlib import Path

from nemik.roundfile import round_text
from nemik.tracker import parse

RECORDED = Path(__file__).parent / "fixtures" / "round" / "round.jsonl"
STAMP = "2026-10-25T09:00:00Z"
ROUNDS = [
    ("alpha", [("W5", 1, "9"), ("W2", 2, "4.5")]),
    ("beta", [("W1", 1, "0.4424")]),
]
HEAD = re.compile(r'^\{"as_of": "[^"]+"\}$')
STAMP_ZONE = re.compile(
    r'"as_of": "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})"'
)


def test_the_writer_reproduces_the_recorded_file_byte_for_byte() -> None:
    """A format change in roundfile fails here, before it reaches an egress rule."""
    assert round_text(STAMP, ROUNDS) == RECORDED.read_text(encoding="utf-8")


def test_the_head_is_exactly_the_stamp_as_the_gate_requires() -> None:
    """The gate's strict header: one object with as_of and nothing else."""
    head = RECORDED.read_text(encoding="utf-8").splitlines()[0]
    assert HEAD.match(head) is not None


def test_every_other_line_is_a_card_with_the_fields_the_readers_use() -> None:
    """Every card line has string repo and symbol fields and an integer-parsable rank."""
    cards = RECORDED.read_text(encoding="utf-8").splitlines()[1:]
    assert cards
    for line in cards:
        card = parse(line)
        assert isinstance(card, dict)
        assert isinstance(card["repo"], str)
        assert isinstance(card["symbol"], str)
        assert isinstance(card["rank"], str)
        assert int(card["rank"]) >= 1


def test_the_stamp_carries_a_zone_as_the_reader_requires() -> None:
    """The reader finds the first as_of by regex and needs an ISO stamp with a zone."""
    assert STAMP_ZONE.search(RECORDED.read_text(encoding="utf-8")) is not None
