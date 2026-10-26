# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1126: the store remembers each ratchet's required fall; no local file loss resets it."""

from nemik.pacepublish import read_pace
from nemik.pacerun import floors_of, pace_document_floored

STAMP = "2026-10-26T19:00:00Z"
FLAT = (
    '{"metric":{"repo":"nemik","ratchet":"mypy-baseline.json"},'
    '"values":[8,8,8,8,8,8,8,8,8,8,8,8],"timestamps":[1,2,3,4,5,6,7,8,9,10,11,12]}\n'
)
REQUIRED = (
    '{"metric":{"repo":"nemik","ratchet":"mypy-baseline.json"},'
    '"values":[2,2,2,1,1],"timestamps":[1,2,3,4,5]}\n'
    '{"metric":{"repo":"mtools","ratchet":".claude/debtplan.json"},'
    '"values":[1,1,0],"timestamps":[1,2,3]}\n'
)
FLOOR = 2
STATED = 5
MYPY = "nemik\nmypy-baseline.json"
DEBT = "mtools\n.claude/debtplan.json"


def test_the_floor_is_the_highest_required_fall_the_store_holds() -> None:
    """The 2-to-1 reset of mypy and the 1-to-0 of debtplan leave their old floors in the store."""
    assert floors_of(REQUIRED) == {MYPY: 2, DEBT: 1}
    assert floors_of("") == {}


def test_a_flat_ratchet_owes_the_floor_the_store_remembers() -> None:
    """With no last file at all, mypy still owes 2, not the 1 its own series would seed."""
    rows = read_pace(pace_document_floored(FLAT, "", STAMP, floors_of(REQUIRED)))[2]
    assert rows[0][4] == FLOOR
    bare = read_pace(pace_document_floored(FLAT, "", STAMP, {}))[2]
    assert bare[0][4] == 1


def test_a_floor_only_raises_what_the_last_file_stated() -> None:
    """A last file stating 5 is not lowered by a store floor of 2."""
    last = (
        '{"as_of": "2026-10-26T00:00:00Z", "window": "10"}\n'
        '{"repo": "nemik", "ratchet": "mypy-baseline.json", "state": "behind", '
        '"observed": "0", "required": "5"}\n'
    )
    rows = read_pace(pace_document_floored(FLAT, last, STAMP, {MYPY: FLOOR}))[2]
    assert rows[0][4] == STATED
