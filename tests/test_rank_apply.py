"""nemik:W427: nemik-rank --apply hands its rows to mikemol-paths-forward --weights-from, never the file."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from nemik import rank


def test_apply_calls_the_queue_writer_with_the_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_run(cmd: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        seen["cmd"] = cmd
        seen["rows"] = json.loads(Path(cmd[-1]).read_text())
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    rows = [{"symbol": "W1", "weight": 3}]
    rank._apply("/q/paths-forward.json", rows)
    cmd = seen["cmd"]
    assert isinstance(cmd, list)
    assert cmd[0] == str(Path(sys.executable).parent / "mikemol-paths-forward")
    assert cmd[1:4] == ["--state", "/q/paths-forward.json", "--weights-from"]
    assert seen["rows"] == rows
    assert not Path(cmd[-1]).exists(), "the temporary rows file is removed"


def test_a_refusing_writer_fails_the_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda cmd, check: subprocess.CompletedProcess(cmd, 2)
    )
    with pytest.raises(SystemExit) as e:
        rank._apply("/q/paths-forward.json", [])
    assert e.value.code == 2
