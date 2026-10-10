"""nemik:W271 (gcalculus:W224): nemik-check --letters finds a letter that sits in the wrong inbox."""

from __future__ import annotations

from pathlib import Path

import pytest

from nemik.check import main
from nemik.letters import headers, misdelivered


def _letter(root: Path, inbox: str, name: str, first: str) -> None:
    path = root / inbox / "inbox" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(first + "\n\nbody\n")


def test_a_letter_must_sit_in_the_inbox_it_names(tmp_path: Path) -> None:
    _letter(tmp_path, "nemik", "ok.md", "gcalculus → nemik: a question")
    _letter(tmp_path, "nemik", "ascii.md", "life -> nemik: arrow in ascii")
    _letter(tmp_path, "paperkit", "wrong.md", "nemik → gcalculus: not for paperkit")
    _letter(tmp_path, "nemik", "ghost.md", "nemik → nowhere: no such workstream")
    _letter(tmp_path, "nemik", "plain.md", "# a title with no addressee")
    addressed, unaddressed = headers(tmp_path)
    assert len(addressed) == 4 and unaddressed == [("nemik", "plain.md")]
    found = misdelivered(addressed, {"nemik", "paperkit", "gcalculus", "life"})
    assert found == [
        "nemik/inbox/ghost.md: from nemik; names nowhere, which is no workstream",
        "paperkit/inbox/wrong.md: from nemik; belongs in gcalculus/inbox",
    ]


def test_fold_proposes_a_waypoint_for_each_letter_no_waypoint_cites(
    tmp_path: Path,
) -> None:
    # nemik:W277: a letter is a waypoint's evidence in file form, so an uncited one is an orphan.
    from nemik.letters import fold_commands

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
    # nemik:W278: what the letter names has landed, so it is answered; one naming an open card is live.
    from nemik.letters import archive_commands, fold_commands

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
    assert move.startswith("mv ") and "done.md" in move and move.endswith("/archive/")


def test_an_old_dated_orphan_is_stale_and_the_scope_is_one_repo(tmp_path: Path) -> None:
    # nemik:W282: each repo migrates its own inbox; a letter nothing cited for N days is archived.
    from datetime import date

    from nemik.letters import archive_commands, fold_commands

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
    assert "2026-08-01-old.md" in move and "life/inbox" not in move
    # without a cutoff nothing is stale, and every letter is live
    assert len(fold_commands(tmp_path, repo="nemik", today=today)) == 2


def test_an_alert_pair_needs_no_card_but_an_unresolved_opened_does(
    tmp_path: Path,
) -> None:
    # nemik:W301 (substrate): luthen's `alert OPENED` / `alert RESOLVED` letters pair by alert id.
    from nemik.letters import archive_commands, fold_commands

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
    assert len(moves) == 2 and all("a02e6095" in m for m in moves)


def test_apply_mints_the_cards_and_archives_the_stale(tmp_path: Path) -> None:
    # nemik:W301: --fold --apply does what --fold prints; a second run finds nothing to do.
    import json
    from datetime import date

    import installed

    from nemik.letters import apply_fold, orphans

    state = tmp_path / "a" / ".claude" / "paths-forward.json"
    state.parent.mkdir(parents=True)
    state.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": str(tmp_path / "a"),
                "counter": 0,
                "residue": [],
                "waypoints": [],
            }
        )
    )
    _letter(tmp_path, "a", "2026-10-09-live.md", "life → a: a live question")
    _letter(tmp_path, "a", "2026-01-01-old.md", "life → a: long ago")
    done = apply_fold(
        tmp_path,
        "a",
        14,
        date(2026, 10, 10),
        writer=installed.script("mikemol-paths-forward")[0],
        env=installed._bin()[1],
    )
    assert any("W1" in line for line in done)
    assert (tmp_path / "a" / "inbox" / "archive" / "2026-01-01-old.md").exists()
    assert orphans(tmp_path, "a") == []


def test_a_peer_waypoint_citing_the_letter_path_owns_it(tmp_path: Path) -> None:
    # nemik:W280: the sender's waiting waypoint cites `<repo>/inbox/<file>` in its evidence.
    from nemik.letters import orphans

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
    tmp_path: Path, capsys
) -> None:
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
    assert stop.value.code == 5
    assert "MISDELIVERED gcalculus/inbox/lost.md" in capsys.readouterr().out
