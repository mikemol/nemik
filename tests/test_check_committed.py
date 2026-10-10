"""nemik:W272 (gcalculus:W224): nemik-check --committed asserts a peer is read at its last commit."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from nemik.check import main

QUEUE = {
    "version": 1,
    "project_root": "/x",
    "counter": 1,
    "residue": [],
    "waypoints": [],
}


def _repo(root: Path, name: str, *, dirty: bool) -> None:
    repo = root / name
    (repo / ".claude").mkdir(parents=True)
    path = repo / ".claude" / "paths-forward.json"
    path.write_text(json.dumps(QUEUE))
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "PATH": "/usr/bin:/bin",
    }
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "q"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, env=env)
    if dirty:
        path.write_text(json.dumps({**QUEUE, "counter": 2}))


def _exit(root: Path, *repos: str) -> int:
    with pytest.raises(SystemExit) as stop:
        main(["--root", str(root), "--committed", *repos])
    return int(str(stop.value.code))


def test_committed_passes_only_when_every_named_queue_is_at_its_last_commit(
    tmp_path: Path,
) -> None:
    _repo(tmp_path, "clean", dirty=False)
    _repo(tmp_path, "edited", dirty=True)
    assert _exit(tmp_path, "clean") == 0
    assert _exit(tmp_path, "edited") == 4
    assert _exit(tmp_path, "clean", "edited") == 4
    assert _exit(tmp_path) == 4  # no names: every repo
