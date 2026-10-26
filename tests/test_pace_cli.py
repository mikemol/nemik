# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1107: `nemik-rank --pace` names the ratchets that are behind and says so by exit code."""

from pathlib import Path

import pytest

from nemik import pacecli
from nemik.pacecli import EXPORT_TREE, pace_exit, pace_lines, show_pace
from nemik.rank import main

HEAD = '{"as_of": "2026-10-26T09:34:35Z", "window": "10"}\n'
BEHIND_ROW = (
    '{"repo": "nemik", "ratchet": "ruff-baseline.json", "state": "behind", '
    '"observed": "0", "required": "3"}\n'
)
OK_ROW = (
    '{"repo": "nemik", "ratchet": "mypy-baseline.json", "state": "ok", '
    '"observed": "5", "required": "2"}\n'
)
UNKNOWN_ROW = (
    '{"repo": "mtools", "ratchet": "x.json", "state": "unknown", '
    '"observed": "0", "required": "0"}\n'
)
BEHIND_LINE = (
    "behind nemik ruff-baseline.json: fell 0 over 10 landings, owes 3 "
    "(pace of 2026-10-26T09:34:35Z)"
)
BEHIND_EXIT = 1
UNREADABLE_EXIT = 2


def test_a_behind_ratchet_gets_one_line_and_an_ok_one_none() -> None:
    """The line names the repo, the ratchet, what fell, what is owed and when it was drawn."""
    assert pace_lines(HEAD + BEHIND_ROW + OK_ROW) == [BEHIND_LINE]


def test_an_unread_ratchet_is_not_a_paid_one() -> None:
    """Unknown prints too: no verdict is not a clean bill."""
    lines = pace_lines(HEAD + UNKNOWN_ROW)
    assert len(lines) == 1
    assert lines[0].startswith("unknown mtools x.json")


def test_the_exit_code_says_behind_clean_or_unreadable(tmp_path: Path) -> None:
    """1 when any ratchet is behind, 0 when none is, 2 when the file cannot be read."""
    pace = tmp_path / "ratchet-pace.json"
    pace.write_text(HEAD + BEHIND_ROW + OK_ROW, encoding="utf-8")
    assert show_pace(tmp_path) == BEHIND_EXIT
    pace.write_text(HEAD + OK_ROW, encoding="utf-8")
    assert show_pace(tmp_path) == 0
    pace.write_text("not a pace file\n", encoding="utf-8")
    assert show_pace(tmp_path) == UNREADABLE_EXIT
    assert show_pace(tmp_path / "missing") == UNREADABLE_EXIT


def test_only_a_command_line_that_asks_for_pace_is_answered(tmp_path: Path) -> None:
    """Without --pace nothing is answered (-1); with it, --root names the tree to read."""
    (tmp_path / "ratchet-pace.json").write_text(HEAD + BEHIND_ROW, encoding="utf-8")
    assert pace_exit(["nemik", "--round"]) == -1
    assert pace_exit(["--pace", "--root", str(tmp_path)]) == BEHIND_EXIT


def test_without_root_the_pace_file_is_read_where_luthen_publishes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default is luthen's export tree, so no caller has to know its directory."""
    luthens = Path.home() / ".local/share/luthen/nemik-export"
    assert luthens == EXPORT_TREE
    monkeypatch.setattr(pacecli, "EXPORT_TREE", tmp_path)
    (tmp_path / "ratchet-pace.json").write_text(HEAD + BEHIND_ROW, encoding="utf-8")
    assert pace_exit(["--pace"]) == BEHIND_EXIT


def test_the_ranking_command_answers_pace_before_it_builds_anything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """nemik-rank --pace --root DIR exits with the pace's code and prints its lines."""
    (tmp_path / "ratchet-pace.json").write_text(HEAD + BEHIND_ROW, encoding="utf-8")
    with pytest.raises(SystemExit) as stopped:
        main(["--pace", "--root", str(tmp_path)])
    assert stopped.value.code == BEHIND_EXIT
    assert BEHIND_LINE in capsys.readouterr().out
