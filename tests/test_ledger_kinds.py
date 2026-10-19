# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W698: the writer's status lines are bookkeeping and leave toil_share where it was."""

from pathlib import Path

from nemik.adapter import KIND_CLASS, NEMIK, ledger_graph
from nemik.history import toil

LINES = (
    '2026-10-12T10:00:00Z  tick  W1  advanced  unblock  "worked"  evidence=commit abc1234\n'
    '2026-10-12T11:00:00Z  peer  W3  minted  -  "asked"  evidence=beta:W9\n'
)
STATUS = '2026-10-12T12:00:00Z  status  W1  blocked>ready  writer  "blocked -> ready"\n'


def test_a_status_line_is_bookkeeping(tmp_path: Path) -> None:
    """The status kind reads as bookkeeping, not unclassified."""
    ledger = tmp_path / "paths-forward.ledger"
    ledger.write_text(LINES + STATUS)
    g, _ = ledger_graph("alpha", ledger)
    classes = sorted(str(o) for o in g.objects(None, NEMIK.effortClass))
    assert KIND_CLASS["status"] == "bookkeeping"
    assert classes == ["bookkeeping", "forecast", "interrupt"]


def test_status_lines_leave_the_toil_share_unchanged(tmp_path: Path) -> None:
    """The weekly toil share is the same with and without status lines."""
    plain = tmp_path / "plain.ledger"
    plain.write_text(LINES)
    withstatus = tmp_path / "status.ledger"
    withstatus.write_text(LINES + STATUS)
    before: list[dict[str, object]] = toil("alpha", plain)
    after: list[dict[str, object]] = toil("alpha", withstatus)
    assert [r["toil_share"] for r in before] == [r["toil_share"] for r in after]
