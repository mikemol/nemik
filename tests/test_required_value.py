# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1129: a required fall clamped to the value is not a reset; a restored one is silent."""

from pathlib import Path

from nemik.pacerun import resets_of

FIXTURES = Path(__file__).parent / "fixtures" / "pace"
RESTORED = FIXTURES / "required-restored.jsonl"
CLAMPED = FIXTURES / "required-clamped.jsonl"
MYPY = "nemik\nmypy-baseline.json"


def test_a_requirement_that_fell_and_was_restored_is_silent() -> None:
    """Mypy 2,2,1,1,2 ends where it began: the restored floor is not a reset."""
    assert resets_of(RESTORED.read_text(encoding="utf-8")) == []


def test_a_requirement_clamped_to_the_value_is_not_a_reset_but_a_loss_is() -> None:
    """Panflute 6 to 1 with the value at 1 is the clamp (W1105); mypy 2 to 1 at 296 is a reset."""
    assert resets_of(CLAMPED.read_text(encoding="utf-8")) == [MYPY]
