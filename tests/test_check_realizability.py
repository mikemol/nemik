"""nemik:W247: `nemik-check --realizability` prints each live waypoint's coordinate and residue."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from installed import script

OPA = os.environ.get("NEMIK_OPA", "opa")
pytestmark = pytest.mark.skipif(shutil.which(OPA) is None, reason="opa not installed")


def _env(opa: str) -> dict[str, str]:
    return {**os.environ, "OPA_BIN": opa}


def _fleet(tmp_path: Path) -> Path:
    repo = tmp_path / "alpha"
    (repo / ".claude").mkdir(parents=True)
    state = repo / ".claude" / "paths-forward.json"
    pf = [*script("mikemol-paths-forward"), "--state", str(state)]
    for args in (
        ["--init"],
        ["--add", "Write the thing", "--next", "write it"],
        ["--add", "Bare card"],
    ):
        assert (
            subprocess.run(
                [*pf, *args], capture_output=True, text=True, check=False
            ).returncode
            == 0
        )
    return tmp_path


def _run(root: Path, opa: str) -> subprocess.CompletedProcess[str]:
    cmd = [*script("nemik-check"), "--realizability", "--root", str(root)]
    return subprocess.run(
        cmd, env=_env(opa), capture_output=True, text=True, check=False
    )


def test_each_live_waypoint_gets_a_coordinate_and_its_residue(tmp_path: Path) -> None:
    done = _run(_fleet(tmp_path), str(Path(shutil.which(OPA) or OPA).resolve()))
    assert done.returncode == 1, done.stdout + done.stderr
    assert "alpha: 2 waypoint(s)" in done.stdout
    assert "alpha:W1  " in done.stdout
    assert "closes by:" in done.stdout


def test_an_absent_opa_is_not_judged_and_never_clean(tmp_path: Path) -> None:
    done = _run(_fleet(tmp_path), str(tmp_path / "no-such-opa"))
    assert done.returncode == 2, done.stdout + done.stderr
    assert "NOT JUDGED alpha" in done.stdout
