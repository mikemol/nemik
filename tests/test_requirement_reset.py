# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1165: a declared reset reads the one requirement it names as the declared new one."""

from nemik.pacerun import pace_document_floored
from nemik.rebaselines import RESETS, reset_table

MYPY = "nemik\nmypy-baseline.json"
VALUES = [5747 - step for step in range(8)]
STAMPS = ",".join(str(1000 + n) for n in range(len(VALUES)))
EXPORT = (
    '{"metric":{"repo":"nemik","ratchet":"mypy-baseline.json"},"values":'
    f"{VALUES},"
    f'"timestamps":[{STAMPS}]}}\n'
)
AT = "2026-10-27T12:00:00Z"


def test_a_requirement_a_reset_names_reads_as_the_declared_new_one() -> None:
    """109 and 73 become 2 and 4; any other level stands, so a later rise is never undone."""
    stated = {MYPY: 109, "nemik\nruff-baseline.json": 73, "nemik\nother": 109}
    assert reset_table(stated, RESETS) == {
        MYPY: 2,
        "nemik\nruff-baseline.json": 4,
        "nemik\nother": 109,
    }
    assert reset_table({MYPY: 5}, RESETS) == {MYPY: 5}


def test_the_reset_keeps_its_reason_and_the_operator_record() -> None:
    """The declaration carries why, and the transcript line that allowed it."""
    reasons = [reason for _, _, _, _, reason in RESETS]
    assert all("107063" in reason and "W1165" in reason for reason in reasons)


def test_the_pace_reads_the_reset_requirement_not_the_store_floor() -> None:
    """The store keeps the highest sample for 30 days; the floor is reset where it is read."""
    text = pace_document_floored(EXPORT, "", AT, {MYPY: 109})
    assert '"required": "2"' in text
    assert '"required": "109"' not in text


def test_a_floor_raised_past_the_reset_level_is_kept() -> None:
    """Only a requirement equal to the declared old one is reset."""
    text = pace_document_floored(EXPORT, "", AT, {MYPY: 110})
    assert '"required": "110"' in text
