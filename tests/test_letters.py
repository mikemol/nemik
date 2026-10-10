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
