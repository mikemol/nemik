"""nemik:W273 (gcalculus:W225): nemik-pins reports how far behind a peer's HEAD a pin is."""

from __future__ import annotations

import subprocess
from pathlib import Path

from nemik.pins import Pin, behind, main, pins

ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "PATH": "/usr/bin:/bin",
}


def _git(repo: Path, *args: str) -> str:
    run = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=ENV,
    )
    return run.stdout.strip()


def _peer(root: Path) -> list[str]:
    peer = root / "peer"
    peer.mkdir()
    _git(peer, "init", "-q")
    shas = []
    for i in range(3):
        (peer / "f").write_text(str(i))
        _git(peer, "add", "-A")
        _git(peer, "commit", "-q", "-m", f"c{i}")
        shas.append(_git(peer, "rev-parse", "HEAD"))
    return shas


def test_a_pin_is_as_far_behind_as_the_peer_has_commits_since(tmp_path: Path) -> None:
    shas = _peer(tmp_path)
    consumer = tmp_path / "app"
    consumer.mkdir()
    (consumer / "pyproject.toml").write_text(
        f'dependencies = ["peer @ git+https://github.com/o/peer.git@{shas[0]}"]\n'
    )
    (consumer / "MODULE.bazel").write_text(
        f"# git+https://github.com/o/ghost@{'a' * 40}\n"
    )
    found = pins(tmp_path)
    assert Pin("app", "peer", shas[0]) in found
    assert behind(tmp_path, Pin("app", "peer", shas[0])) == 2
    assert behind(tmp_path, Pin("app", "peer", shas[2])) == 0
    assert behind(tmp_path, Pin("app", "ghost", "a" * 40)) is None  # not cloned here


def test_the_command_exits_6_only_past_the_threshold(tmp_path: Path, capsys) -> None:
    shas = _peer(tmp_path)
    consumer = tmp_path / "app"
    consumer.mkdir()
    (consumer / "pyproject.toml").write_text(
        f'x = "git+https://github.com/o/peer@{shas[0]}"\n'
    )
    assert main(["--root", str(tmp_path)]) == 0
    assert "app pins peer@" in capsys.readouterr().out
    assert main(["--root", str(tmp_path), "--max-behind", "2"]) == 0
    assert main(["--root", str(tmp_path), "--max-behind", "1"]) == 6
