"""nemik:W251: the fleet's recorded gaps, by card, from the pinned policy."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from installed import script

from nemik.residue import by_card

OPA = os.environ.get("NEMIK_OPA", "opa")
pytestmark = pytest.mark.skipif(shutil.which(OPA) is None, reason="opa not installed")


def _fleet(tmp_path: Path) -> Path:
    (tmp_path / "alpha" / ".claude").mkdir(parents=True)
    state = tmp_path / "alpha" / ".claude" / "paths-forward.json"
    pf = [*script("mikemol-paths-forward"), "--state", str(state)]
    for args in (
        ["--init"],
        ["--add", "Write it", "--next", "write it"],
        ["--add", "Bare"],
    ):
        assert (
            subprocess.run(
                pf + args, capture_output=True, text=True, check=False
            ).returncode
            == 0
        )
    return tmp_path


def test_every_judged_card_with_a_gap_is_keyed_by_its_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPA_BIN", str(Path(shutil.which(OPA) or OPA).resolve()))
    gaps = by_card(_fleet(tmp_path))
    assert set(gaps) == {"alpha:W1", "alpha:W2"}
    assert all(entry.get("gate") for entries in gaps.values() for entry in entries)


def test_an_absent_opa_raises_rather_than_reporting_no_gaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mikemol.pathsforward.opa_eval import OpaUnavailableError

    monkeypatch.setenv("OPA_BIN", str(tmp_path / "no-such-opa"))
    with pytest.raises(OpaUnavailableError):
        by_card(_fleet(tmp_path))
