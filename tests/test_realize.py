"""nemik:W246: nemik.realize judges every live waypoint in one batch and never reads an unjudged one as clean."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from installed import script

from nemik.realize import verdicts

OPA = os.environ.get("NEMIK_OPA", "opa")
pytestmark = pytest.mark.skipif(shutil.which(OPA) is None, reason="opa not installed")
NOW = "2026-10-08T12:00:00Z"


def _pf(state: Path, *args: str) -> None:
    cmd = [*script("mikemol-paths-forward"), "--state", str(state), *args]
    assert (
        subprocess.run(cmd, capture_output=True, text=True, check=False).returncode == 0
    )


def _queue(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir()
    state = tmp_path / ".claude" / "paths-forward.json"
    _pf(state, "--init")
    _pf(state, "--add", "Write the thing", "--next", "write it")
    _pf(state, "--add", "Another thing")
    _pf(state, "--add", "Finished thing", "--next", "none")
    _pf(state, "--update", "W3", "--status", "done")
    return state


def test_every_live_waypoint_is_judged_and_a_done_one_is_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPA_BIN", str(Path(shutil.which(OPA) or OPA).resolve()))
    found = verdicts(_queue(tmp_path), tmp_path, NOW)
    assert [str(v["ref"]).rsplit(":", 1)[-1] for v in found] == ["W1", "W2"]


def test_an_absent_opa_raises_rather_than_reading_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mikemol.pathsforward.opa_eval import OpaUnavailableError

    monkeypatch.setenv("OPA_BIN", str(tmp_path / "no-such-opa"))
    with pytest.raises(OpaUnavailableError):
        verdicts(_queue(tmp_path), tmp_path, NOW)
