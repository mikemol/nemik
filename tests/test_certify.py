"""nemik:W245: mtools' realizability batch (`--certify`) runs under the hash-pinned opa.

The policy ships in the pinned pathsforward wheel (nemik:W230, mtools:W850). This test is the
nemik-side witness that the installed wheel and the bazel `@opa` agree: a fixture queue goes in,
one verdict per waypoint comes out, and an absent field is residue, never clean.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from installed import script

OPA = os.environ.get("NEMIK_OPA", "opa")
pytestmark = pytest.mark.skipif(shutil.which(OPA) is None, reason="opa not installed")


def _pf(state: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OPA_BIN": str(Path(shutil.which(OPA) or OPA).resolve())}
    cmd = [*script("mikemol-paths-forward"), "--state", str(state), *args]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)


def _queue(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir()
    state = tmp_path / ".claude" / "paths-forward.json"
    assert _pf(state, "--init").returncode == 0
    assert _pf(state, "--add", "Write the thing", "--next", "write it").returncode == 0
    assert _pf(state, "--add", "Another thing").returncode == 0
    return state


def test_certify_judges_each_waypoint_in_one_batch(tmp_path: Path) -> None:
    done = _pf(_queue(tmp_path), "--certify", "W1", "W2")
    lines = done.stdout.splitlines() + done.stderr.splitlines()
    verdicts = [json.loads(ln) for ln in lines if ln.startswith("{")]
    assert [v["ref"].rsplit(":", 1)[-1] for v in verdicts] == ["W1", "W2"]
    assert all(
        {"ref", "level", "reference_arm", "residue"} <= v.keys() for v in verdicts
    )


def test_an_absent_field_is_residue_not_clean(tmp_path: Path) -> None:
    done = _pf(_queue(tmp_path), "--certify", "W1", "W2")
    assert done.returncode != 0, "a queue with residue must not exit clean"
    lines = done.stdout.splitlines() + done.stderr.splitlines()
    by_ref = {
        v["ref"].rsplit(":", 1)[-1]: v
        for v in map(json.loads, (ln for ln in lines if ln.startswith("{")))
    }
    assert any(r["gate"] == "coverable" for r in by_ref["W1"]["residue"])
    assert by_ref["W2"]["level"] == "none"
    assert any(r["gate"] == "constructible" for r in by_ref["W2"]["residue"])
