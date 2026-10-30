# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W273 (gcalculus:W225): nemik-pins reports how far behind a peer's HEAD a pin is."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from nemik.pins import Pin, behind, main, pins

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

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
    """A pin is as far behind as the peer has commits since."""
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


def test_a_vendored_wheel_names_its_mtools_commit_in_its_file_name(
    tmp_path: Path,
) -> None:
    """A vendored wheel names its mtools commit in its file name."""
    # nemik:W303: nemik pins mtools by wheel (vendor/wheels/mikemol_*-0.1.0+<sha>-...), not a git
    # URL.
    consumer = tmp_path / "app"
    consumer.mkdir()
    (consumer / "pyproject.toml").write_text(
        'a = { path = "vendor/wheels/mikemol_hooks-0.1.0+842ab10-py3-none-any.whl" }\n'
        'b = { path = "vendor/wheels/mikemol_icsstruct-0.1.0+842ab10-py3-none-any.whl" }\n'
    )
    assert pins(tmp_path) == [Pin("app", "mtools", "842ab10")]  # one pin: one commit


def test_the_command_exits_6_only_past_the_threshold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command exits 6 only past the threshold."""
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
