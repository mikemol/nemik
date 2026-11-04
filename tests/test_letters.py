# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W271 (gcalculus:W224): nemik-check --letters finds a letter in the wrong inbox."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

import installed
import pytest

from nemik.check import main
from nemik.letters import (
    apply_fold,
    archive_commands,
    fold_commands,
    headers,
    misdelivered,
    orphans,
    report,
)

if TYPE_CHECKING:
    from pathlib import Path

ADDRESSED = 4
FOLDS_FOR_NEMIK = 2
MOVES = 2
EXIT_LETTERS_PENDING = 5


def _letter(root: Path, inbox: str, name: str, first: str) -> None:
    path = root / inbox / "inbox" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(first + "\n\nbody\n")


def test_a_letter_must_sit_in_the_inbox_it_names(tmp_path: Path) -> None:
    """A letter must sit in the inbox it names."""
    _letter(tmp_path, "nemik", "ok.md", "gcalculus → nemik: a question")
    _letter(tmp_path, "nemik", "ascii.md", "life -> nemik: arrow in ascii")
    _letter(tmp_path, "paperkit", "wrong.md", "nemik → gcalculus: not for paperkit")
    _letter(tmp_path, "nemik", "ghost.md", "nemik → nowhere: no such workstream")
    _letter(tmp_path, "nemik", "plain.md", "# a title with no addressee")
    addressed, unaddressed = headers(tmp_path)
    assert len(addressed) == ADDRESSED
    assert unaddressed == [("nemik", "plain.md")]
    found = misdelivered(addressed, {"nemik", "paperkit", "gcalculus", "life"})
    assert found == [
        "nemik/inbox/ghost.md: from nemik; names nowhere, which is no workstream",
        "paperkit/inbox/wrong.md: from nemik; belongs in gcalculus/inbox",
    ]


def test_fold_proposes_a_waypoint_for_each_letter_no_waypoint_cites(
    tmp_path: Path,
) -> None:
    """Fold proposes a waypoint for each letter no waypoint cites."""
    # nemik:W277: a letter is a waypoint's evidence in file form, so an uncited one is an orphan.

    queue = tmp_path / "nemik" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    queue.write_text(
        '{"version": 1, "project_root": "/x", "counter": 1, "residue": [],'
        ' "waypoints": [{"symbol": "W1", "title": "t", "status": "ready",'
        ' "caused_by": "inbox/cited.md"}]}'
    )
    _letter(tmp_path, "nemik", "cited.md", "gcalculus → nemik: already owned")
    _letter(tmp_path, "nemik", "loose.md", "life → nemik: a question")
    (cmd,) = fold_commands(tmp_path)
    assert "--add 'Answer life: a question'" in cmd
    assert cmd.endswith("--caused-by inbox/loose.md")
    assert str(queue) in cmd


def test_an_orphan_whose_waypoints_are_all_closed_is_archived_not_folded(
    tmp_path: Path,
) -> None:
    """An orphan whose waypoints are all closed is archived not folded."""
    # nemik:W278: what the letter names has landed, so it is answered; one naming an open card is
    # live.

    queue = tmp_path / "nemik" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    queue.write_text(
        '{"version": 1, "project_root": "/x", "counter": 2, "residue": [],'
        ' "waypoints": [{"symbol": "W1", "title": "t", "status": "done"},'
        ' {"symbol": "W2", "title": "u", "status": "ready"}]}'
    )
    _letter(tmp_path, "nemik", "done.md", "life → nemik: about nemik:W1")
    _letter(tmp_path, "nemik", "open.md", "life → nemik: about nemik:W2")
    assert len(fold_commands(tmp_path)) == 1
    assert "--caused-by inbox/open.md" in fold_commands(tmp_path)[0]
    (move,) = archive_commands(tmp_path)
    assert move.startswith("mv ")
    assert "done.md" in move
    assert move.endswith("/archive/")


def test_an_old_dated_orphan_is_stale_and_the_scope_is_one_repo(tmp_path: Path) -> None:
    """An old dated orphan is stale and the scope is one repo."""
    # nemik:W282: each repo migrates its own inbox; a letter nothing cited for N days is archived.

    for repo in ("nemik", "life"):
        queue = tmp_path / repo / ".claude" / "paths-forward.json"
        queue.parent.mkdir(parents=True)
        queue.write_text(
            '{"version": 1, "project_root": "/x", "counter": 0, "residue": [],'
            ' "waypoints": []}'
        )
    _letter(tmp_path, "nemik", "2026-08-01-old.md", "life → nemik: long ago")
    _letter(tmp_path, "nemik", "2026-10-09-new.md", "life → nemik: yesterday")
    _letter(tmp_path, "life", "2026-08-01-other.md", "nemik → life: not nemik's")
    today = date(2026, 10, 10)
    (add,) = fold_commands(tmp_path, repo="nemik", older_than=14, today=today)
    assert "2026-10-09-new.md" in add
    (move,) = archive_commands(tmp_path, repo="nemik", older_than=14, today=today)
    assert "2026-08-01-old.md" in move
    assert "life/inbox" not in move
    # without a cutoff nothing is stale, and every letter is live
    assert len(fold_commands(tmp_path, repo="nemik", today=today)) == FOLDS_FOR_NEMIK


def test_an_alert_pair_needs_no_card_but_an_unresolved_opened_does(
    tmp_path: Path,
) -> None:
    """An alert pair needs no card but an unresolved opened does."""
    # nemik:W301 (substrate): luthen's `alert OPENED` / `alert RESOLVED` letters pair by alert id.

    queue = tmp_path / "substrate" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    queue.write_text(
        '{"version": 1, "project_root": "/x", "counter": 0, "residue": [],'
        ' "waypoints": []}'
    )
    for name in (
        "2026-09-24-luthen-alert-fell-opened-a02e6095.md",
        "2026-09-24-luthen-alert-fell-resolved-a02e6095.md",
        "2026-10-06-luthen-alert-stalled-opened-bbbb1111.md",
    ):
        _letter(tmp_path, "substrate", name, "luthen → substrate: alert")
    (card,) = fold_commands(tmp_path, repo="substrate")
    assert "stalled-opened-bbbb1111" in card  # no RESOLVED twin: still a card
    moves = archive_commands(tmp_path, repo="substrate")
    assert len(moves) == MOVES
    assert all("a02e6095" in m for m in moves)


def test_apply_mints_the_cards_and_archives_the_stale(tmp_path: Path) -> None:
    """nemik:W301: applying the fold mints a card for the live letter and archives the stale one."""
    state = tmp_path / "a" / ".claude" / "paths-forward.json"
    state.parent.mkdir(parents=True)
    body: dict[str, object] = {
        "version": 1,
        "project_root": str(tmp_path / "a"),
        "counter": 0,
        "residue": [],
        "waypoints": [],
    }
    state.write_text(json.dumps(body))
    _letter(tmp_path, "a", "2026-10-09-live.md", "life → a: a live question")
    _letter(tmp_path, "a", "2026-01-01-old.md", "life → a: long ago")
    done = apply_fold(
        tmp_path,
        ("a", 14),
        today=date(2026, 10, 10),
        writer=installed.script("mikemol-paths-forward")[0],
        env=installed.bin_env()[1],
    )
    assert any("W1" in line for line in done)
    assert (tmp_path / "a" / "inbox" / "archive" / "2026-01-01-old.md").exists()
    assert orphans(tmp_path, "a") == []


def test_a_misdelivered_letter_is_copied_to_its_recipient_and_then_counts_as_delivered(
    tmp_path: Path,
) -> None:
    """A misdelivered letter is copied to its recipient and then counts as delivered."""
    # nemik:W310: a letter addressed to linux-sources that sits in gcalculus/inbox is copied over.
    for repo in ("gcalculus", "linux-sources"):
        queue = tmp_path / repo / ".claude" / "paths-forward.json"
        queue.parent.mkdir(parents=True)
        queue.write_text(
            '{"version": 1, "project_root": "/x", "counter": 0, "residue": [],'
            ' "waypoints": []}'
        )
        (tmp_path / repo / "inbox").mkdir()
    _letter(
        tmp_path, "gcalculus", "2026-08-21-misfiled.md", "gcalculus → linux-sources: x"
    )

    spaces = {"gcalculus", "linux-sources"}
    said, code = report(tmp_path, spaces, fold=True, scope=("linux-sources", None))
    assert code == EXIT_LETTERS_PENDING
    assert any(line.startswith("cp ") for line in said)
    said, code = report(
        tmp_path, spaces, fold=True, scope=("linux-sources", None), apply=True
    )
    assert any(line.startswith("delivered ") for line in said)
    assert code == 0  # the apply run's own verdict is the after state
    copy = tmp_path / "linux-sources" / "inbox" / "2026-08-21-misfiled.md"
    assert copy.exists()
    # the recipient reads it and files it under archive/: still delivered, not misdelivered again
    (copy.parent / "archive").mkdir()
    copy.rename(copy.parent / "archive" / copy.name)
    assert report(tmp_path, spaces, fold=True, scope=("linux-sources", None))[1] == 0


def test_a_peer_waypoint_citing_the_letter_path_owns_it(tmp_path: Path) -> None:
    """nemik:W280: the sender's waiting waypoint cites `<repo>/inbox/<file>` in its evidence.

    So the cited letter is owned and only the uncited one is an orphan.
    """
    for repo, evidence in (("nemik", ""), ("life", "Letter: nemik/inbox/asked.md")):
        queue = tmp_path / repo / ".claude" / "paths-forward.json"
        queue.parent.mkdir(parents=True)
        queue.write_text(
            '{"version": 1, "project_root": "/x", "counter": 1, "residue": [],'
            ' "waypoints": [{"symbol": "W1", "title": "t", "status": "ready",'
            f' "evidence": "{evidence}"}}]}}'
        )
    _letter(tmp_path, "nemik", "asked.md", "life → nemik: cited by the sender")
    _letter(tmp_path, "nemik", "loose.md", "life → nemik: cited by nobody")
    assert [path.name for _, path, _ in orphans(tmp_path)] == ["loose.md"]


def test_the_command_exits_5_only_when_a_letter_is_misdelivered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command exits 5 only when a letter is misdelivered."""
    for repo in ("nemik", "gcalculus"):
        queue = tmp_path / repo / ".claude" / "paths-forward.json"
        queue.parent.mkdir(parents=True)
        queue.write_text(
            '{"version": 1, "project_root": "/x", "counter": 0,'
            ' "residue": [], "waypoints": []}'
        )
    _letter(tmp_path, "nemik", "ok.md", "gcalculus → nemik: fine")
    with pytest.raises(SystemExit) as clean:
        main(["--root", str(tmp_path), "--letters"])
    assert clean.value.code == 0
    _letter(tmp_path, "gcalculus", "lost.md", "life → nemik: wrong inbox")
    with pytest.raises(SystemExit) as stop:
        main(["--root", str(tmp_path), "--letters"])
    assert stop.value.code == EXIT_LETTERS_PENDING
    assert "MISDELIVERED gcalculus/inbox/lost.md" in capsys.readouterr().out


def test_a_corrupt_queue_is_refused_not_read_as_owning_nothing(tmp_path: Path) -> None:
    """A queue that parses to a non-object raises TypeError, so no orphan is hidden or invented."""
    _letter(tmp_path, "alpha", "2026-10-01-note.md", "# note")
    state = tmp_path / "alpha" / ".claude" / "paths-forward.json"
    state.parent.mkdir(parents=True)
    state.write_text("[]")
    with pytest.raises(TypeError, match="queue object"):
        orphans(tmp_path)
    state.write_text("{not json")
    assert orphans(tmp_path) == [
        ("alpha", tmp_path / "alpha/inbox/2026-10-01-note.md", False)
    ]
