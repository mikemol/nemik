# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W990: the private build publishes the ratchet pace board and gauges from the pace file."""

import shutil
from pathlib import Path

from nemik.serve import PACE_FILE, fleet_key, publish

FLEET = Path(__file__).parent / "fixtures" / "fleet"
PACE = (
    '{"as_of": "2026-10-24T19:00:00Z", "window": "10", "rows": [\n'
    '  {"repo": "nemik", "ratchet": "ruff-baseline.json", "state": "behind",'
    ' "observed": "0", "required": "3"}\n'
    "]}\n"
)


def _fleet(tmp_path: Path) -> Path:
    root = tmp_path / "fleet"
    shutil.copytree(FLEET, root)
    return root


def test_a_pace_file_is_published_as_board_and_gauges(tmp_path: Path) -> None:
    """The board holds the row, and metrics carries the behind gauge with value 1."""
    root = _fleet(tmp_path)
    (root / PACE_FILE).write_text(PACE)
    snap = publish(root, tmp_path / "pub", None)
    assert snap is not None
    assert '"host": true' in (snap / "ratchet-pace.json").read_text()
    gauge = 'nemik_ratchet_behind{repo="nemik",ratchet="ruff-baseline.json"} 1'
    assert gauge in (snap / "metrics").read_text()
    assert "nemik_ratchet_pace_as_of " in (snap / "metrics").read_text()


def test_no_pace_file_publishes_a_board_that_says_so(tmp_path: Path) -> None:
    """Without the file there is no board and no ratchet gauge, never a guessed one."""
    snap = publish(_fleet(tmp_path), tmp_path / "pub", None)
    assert snap is not None
    assert '"host": false' in (snap / "ratchet-pace.json").read_text()
    assert "nemik_ratchet_behind{" not in (snap / "metrics").read_text()


def test_a_changed_pace_file_changes_the_fleet_key(tmp_path: Path) -> None:
    """The builder rebuilds when the pace changes, not only when a queue does."""
    root = _fleet(tmp_path)
    before = fleet_key(root)
    (root / PACE_FILE).write_text(PACE)
    assert fleet_key(root) != before
