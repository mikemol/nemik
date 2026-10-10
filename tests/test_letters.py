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
