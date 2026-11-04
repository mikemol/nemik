# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W427: nemik-rank --apply hands its rows to the writer's --weights-from, never the file."""

import json
import sys
from pathlib import Path

import pytest
from mikemol.procrun.proc import Completed

from nemik import rank

EXIT_REFUSED = 2


def test_apply_calls_the_queue_writer_with_the_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apply calls the queue writer with the rows."""
    cmds: list[list[str]] = []
    read_rows: list[object] = []

    def fake_run(cmd: list[str], **_kwargs: object) -> Completed:
        cmds.append(cmd)
        rows_read: object = json.loads(Path(cmd[-1]).read_text(encoding="utf-8"))
        read_rows.append(rows_read)
        return Completed(cmd, 0, "", "")

    monkeypatch.setattr(rank, "capture", fake_run)
    rows: list[rank.RankRow] = [{"symbol": "W1", "weight": 3}]
    rank.apply_weights("/q/paths-forward.json", rows)
    (cmd,) = cmds
    assert cmd[0] == str(Path(sys.executable).parent / "mikemol-paths-forward")
    assert cmd[1:4] == ["--state", "/q/paths-forward.json", "--weights-from"]
    assert read_rows == [rows]
    assert not Path(cmd[-1]).exists(), "the temporary rows file is removed"


def test_a_refusing_writer_fails_the_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """A refusing writer fails the command."""

    def refuse(cmd: list[str], **_kwargs: object) -> Completed:
        return Completed(cmd, 2, "", "")

    monkeypatch.setattr(rank, "capture", refuse)
    with pytest.raises(SystemExit) as e:
        rank.apply_weights("/q/paths-forward.json", [])
    assert e.value.code == EXIT_REFUSED
