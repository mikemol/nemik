# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W978: the pod's build publishes the landings board from the file in its root."""

import shutil
from pathlib import Path

from nemik.landings import Landing, document
from nemik.serve import LANDINGS_FILE, fleet_key, publish

FLEET = Path(__file__).parent / "fixtures" / "fleet"
ROWS = [Landing("alpha", "abc1234", "W1", 120, "2026-10-24T10:00:00Z")]


def _fleet(tmp_path: Path) -> Path:
    root = tmp_path / "fleet"
    shutil.copytree(FLEET, root)
    return root


def test_a_landings_file_in_the_root_is_published_as_the_board(tmp_path: Path) -> None:
    """The private build writes landings.json with the file's rows, as the live server would."""
    root = _fleet(tmp_path)
    (root / LANDINGS_FILE).write_text(document(ROWS, "2026-10-24T10:05:00Z"))
    snap = publish(root, tmp_path / "pub", None)
    assert snap is not None
    board = (snap / "landings.json").read_text()
    assert '"host": true' in board
    assert '"sha": "abc1234"' in board


def test_no_landings_file_publishes_a_board_that_says_so(tmp_path: Path) -> None:
    """Without the file the board is absent with a reason, never a guessed one."""
    snap = publish(_fleet(tmp_path), tmp_path / "pub", None)
    assert snap is not None
    assert '"host": false' in (snap / "landings.json").read_text()


def test_a_changed_landings_file_changes_the_fleet_key(tmp_path: Path) -> None:
    """The builder rebuilds when the landings change, not only when a queue does."""
    root = _fleet(tmp_path)
    before = fleet_key(root)
    (root / LANDINGS_FILE).write_text(document(ROWS, "2026-10-24T10:05:00Z"))
    assert fleet_key(root) != before
