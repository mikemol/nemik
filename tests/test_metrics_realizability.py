"""nemik:W232: nemik-metrics exposes the realizability coordinate counts, and an unjudged queue is flagged."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from installed import script

from nemik.metrics import realizability_lines

OPA = os.environ.get("NEMIK_OPA", "opa")
pytestmark = pytest.mark.skipif(shutil.which(OPA) is None, reason="opa not installed")


def _fleet(tmp_path: Path) -> Path:
    repo = tmp_path / "alpha"
    (repo / ".claude").mkdir(parents=True)
    state = repo / ".claude" / "paths-forward.json"
    pf = [*script("mikemol-paths-forward"), "--state", str(state)]
    for args in (["--init"], ["--add", "Write the thing", "--next", "write it"]):
        assert (
            subprocess.run(
                [*pf, *args], capture_output=True, text=True, check=False
            ).returncode
            == 0
        )
    return tmp_path


def test_each_coordinate_is_counted_per_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPA_BIN", str(Path(shutil.which(OPA) or OPA).resolve()))
    lines = realizability_lines(_fleet(tmp_path))
    counted = [ln for ln in lines if ln.startswith("nemik_realizability_waypoints{")]
    assert len(counted) == 1, lines
    assert counted[0].startswith(
        'nemik_realizability_waypoints{repo="alpha",coordinate="'
    )
    assert counted[0].endswith("} 1")
    assert not any(ln.startswith("nemik_realizability_unjudged{") for ln in lines)


def test_an_unjudged_queue_is_flagged_not_zeroed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPA_BIN", str(tmp_path / "no-such-opa"))
    lines = realizability_lines(_fleet(tmp_path))
    assert 'nemik_realizability_unjudged{repo="alpha"} 1' in lines
    assert not any(ln.startswith("nemik_realizability_waypoints{") for ln in lines)
