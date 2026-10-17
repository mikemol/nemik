# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W625: the readers keep the SHACL and flow caches in the user's cache directory."""

import json
import shutil
from pathlib import Path

import pytest

from nemik import cachestore
from nemik.check import survey

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_the_directory_follows_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """NEMIK_CACHE_DIR wins, then XDG_CACHE_HOME/nemik."""
    monkeypatch.setenv("NEMIK_CACHE_DIR", str(tmp_path / "named"))
    assert cachestore.user_dir() == tmp_path / "named"
    monkeypatch.delenv("NEMIK_CACHE_DIR")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert cachestore.user_dir() == tmp_path / "xdg" / "nemik"


def test_a_survey_of_the_real_root_keeps_its_caches_and_a_later_process_loads_them(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With the fixture fleet as the root, one survey writes the file; a fresh restore loads it."""
    monkeypatch.setenv("NEMIK_ROOT", str(FLEET))
    monkeypatch.setenv("NEMIK_CACHE_DIR", str(tmp_path))
    cachestore.RESTORED[0] = False
    assert not (tmp_path / cachestore.NAME).exists()
    assert sum(1 for _ in survey(FLEET)) > 0
    assert (tmp_path / cachestore.NAME).exists()
    cachestore.RESTORED[0] = False
    assert cachestore.restore_user()


def _verdicts(root: Path) -> list[tuple[str, str, str, str]]:
    """Collect every finding a survey of the root reports.

    Args:
        root: The fleet root.

    Returns:
        (repo, severity, symbol, message) rows, sorted.

    """
    return sorted(
        (repo, sev, sym, msg)
        for repo, _, found in survey(root)
        for sev, sym, msg in found
    )


def test_an_edit_between_two_runs_shows_in_the_second(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A queue edit never returns last run's verdict (github-8f's check).

    After nemik's queue is replaced between two runs, the warm second run reports exactly what a
    cold full run of an identical copy of the edited tree reports, and differs from the first run.
    """
    fleet = tmp_path / "fleet"
    shutil.copytree(FLEET, fleet)
    monkeypatch.setenv("NEMIK_ROOT", str(fleet))
    monkeypatch.setenv("NEMIK_CACHE_DIR", str(tmp_path / "cache"))
    cachestore.RESTORED[0] = False
    first = _verdicts(fleet)
    residue: list[str] = []
    card: dict[str, object] = {
        "symbol": "W1",
        "title": "t",
        "status": "ready",
        "next_bounded_step": "x",
    }
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/nemik",
        "counter": 1,
        "residue": residue,
        "waypoints": [card],
    }
    (fleet / "nemik" / "paths-forward.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    second = _verdicts(fleet)
    twin = tmp_path / "twin"
    shutil.copytree(fleet, twin)
    assert second == _verdicts(twin)
    assert second != first


def test_a_survey_of_another_root_leaves_the_directory_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A temporary root is not the fleet: it must not grow the user's cache."""
    monkeypatch.setenv("NEMIK_ROOT", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("NEMIK_CACHE_DIR", str(tmp_path / "cache"))
    assert sum(1 for _ in survey(FLEET)) > 0
    assert not (tmp_path / "cache").exists()
