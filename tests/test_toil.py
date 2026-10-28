# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W314: nemik-history --toil reports the weekly interrupt share from a repo's ledger."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nemik.history import toil

if TYPE_CHECKING:
    from pathlib import Path

LEDGER = (
    '2026-10-05T10:00:00Z  tick  W1  advanced  unblock  "planned one"\n'
    '2026-10-06T10:00:00Z  tick  W2  advanced  unblock  "planned two"\n'
    '2026-10-07T10:00:00Z  peer  W3  advanced  unblock  "a fire"\n'
    '2026-10-13T10:00:00Z  tick  W4  advanced  unblock  "next week, all planned"\n'
)


def test_the_interrupt_share_is_unplanned_over_planned_plus_unplanned(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "paths-forward.ledger"
    ledger.write_text(LEDGER)
    first, second = toil("a", ledger)
    assert first["week"] == "2026-W41" and second["week"] == "2026-W42"
    assert first["toil_share"] == 0.333  # one interrupt among three
    assert second["toil_share"] == 0.0
