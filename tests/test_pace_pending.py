# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1284: a pace older than the repo's newest landing is printed PENDING, with both times."""

from pathlib import Path

import pytest

from nemik.pacecli import (
    epoch_of,
    iso_of,
    newest_landing,
    pace_exit,
    show_pace,
)

# stack 694's landing in nemik's own reflog: 2026-10-30 00:57:32 -0400
LANDED = 1793336252
EARLIER = 1793333348
LANDED_ISO = "2026-10-30T04:57:32Z"
OLD_PACE = "2026-10-30T04:25:12Z"
NEW_PACE = "2026-10-30T05:25:11Z"
ROW = (
    '{"repo": "nemik", "ratchet": "ruff-baseline.json", "state": "behind", '
    '"observed": "34", "required": "73"}\n'
)
OK_ROW = (
    '{"repo": "nemik", "ratchet": "mypy-baseline.json", "state": "ok", '
    '"observed": "5", "required": "2", "value": "3548", "horizon": "99"}\n'
)
UNKNOWN_ROW = (
    '{"repo": "mtools", "ratchet": "x.json", "state": "unknown", '
    '"observed": "0", "required": "0"}\n'
)
BEHIND_EXIT = 1


def _tree(tmp_path: Path, as_of: str) -> Path:
    """Write a pace file stamped `as_of` under a temporary export tree.

    Returns:
        The export tree.

    """
    (tmp_path / "ratchet-pace.json").write_text(
        f'{{"as_of": "{as_of}", "window": "10"}}\n{ROW}{OK_ROW}{UNKNOWN_ROW}'
    )
    return tmp_path


def _line(epoch: int) -> str:
    """Write one reflog line as git does: ids, author, epoch, zone, a tab and the message.

    Returns:
        The line.

    """
    return f"{'a' * 40} {'b' * 40} Mike Mol <m@x> {epoch} -0400\tmikemol-commit stack\n"


def test_a_stamp_and_its_epoch_round_trip() -> None:
    """The reflog's own epoch and the stamp the pace prints name the same instant."""
    assert epoch_of(LANDED_ISO) == LANDED
    assert iso_of(LANDED) == LANDED_ISO
    for epoch in (0, 951_782_400, LANDED, 4_102_444_799):
        assert epoch_of(iso_of(epoch)) == epoch
    assert epoch_of("not a stamp") == 0
    assert epoch_of("2026-10-30 04:57:32") == 0


def test_the_newest_landing_is_the_last_reflog_line(tmp_path: Path) -> None:
    """The epoch is the second-to-last word before the tab; a missing or empty log reads 0."""
    log = tmp_path / ".git" / "logs" / "refs" / "heads"
    log.mkdir(parents=True)
    (log / "main").write_text(_line(EARLIER) + _line(LANDED))
    assert newest_landing(tmp_path) == LANDED
    (log / "main").write_text("")
    assert newest_landing(tmp_path) == 0
    assert newest_landing(tmp_path / "absent") == 0


def test_a_pace_older_than_the_landing_marks_every_line_pending(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The header gives both times and the verdict; the behind and the ok lines both say PENDING."""
    code = show_pace(_tree(tmp_path, OLD_PACE), LANDED, "nemik")
    lines = capsys.readouterr().out.splitlines()
    assert code == BEHIND_EXIT
    assert lines[0] == (
        f"pace of {OLD_PACE}; newest landing of nemik {LANDED_ISO}: PENDING"
    )
    assert lines[1:]
    own = [line for line in lines[1:] if " nemik " in line]
    other = [line for line in lines[1:] if " mtools " in line]
    assert own
    assert all(line.startswith("PENDING ") for line in own)
    assert other
    assert not any(line.startswith("PENDING") for line in other)


def test_a_pace_newer_than_the_landing_is_current_and_unmarked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pace that postdates the landing says current and leaves its lines as they were."""
    show_pace(_tree(tmp_path, NEW_PACE), LANDED, "nemik")
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].endswith(": current")
    assert not any(line.startswith("PENDING") for line in lines)


def test_without_a_landing_the_output_is_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No repo named means no header and no mark, as before nemik:W1284."""
    show_pace(_tree(tmp_path, OLD_PACE))
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("behind nemik ruff-baseline.json")
    assert not any("PENDING" in line or "newest landing" in line for line in lines)


def test_the_repo_is_the_first_word_that_is_not_an_option(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The value after --root is a path, not a repo: with none named there is no header."""
    tree = _tree(tmp_path, OLD_PACE)
    assert pace_exit(["--pace", "--root", str(tree)]) == BEHIND_EXIT
    assert "newest landing" not in capsys.readouterr().out
