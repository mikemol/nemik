# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W594: nemik-replica reads the result line and the pushed sha from a .git directory."""

from pathlib import Path

from nemik.replica_cli import main, pushed_sha, report, shipped

SHA = "c" * 40


def _gitdir(root: Path, last: str, layout: str) -> Path:
    """Make a .git directory with a pushed ref and, optionally, a result line.

    Args:
        root: A scratch directory, created if absent.
        last: The result line, or empty for none.
        layout: packed for packed-refs, loose for a ref file.

    Returns:
        The .git directory.

    """
    gitdir = root / ".git"
    gitdir.mkdir(parents=True)
    if layout == "packed":
        (gitdir / "packed-refs").write_text(
            f"# pack-refs\n{SHA} refs/remotes/origin/main\n", encoding="utf-8"
        )
    else:
        ref = gitdir / "refs" / "remotes" / "origin" / "main"
        ref.parent.mkdir(parents=True)
        ref.write_text(SHA + "\n", encoding="utf-8")
    if last:
        (gitdir / "image-replica.last").write_text(last, encoding="utf-8")
    return gitdir


def test_the_pushed_sha_is_read_loose_or_packed(tmp_path: Path) -> None:
    """Either place a git keeps a remote-tracking ref."""
    assert pushed_sha(_gitdir(tmp_path / "a", "", "packed")) == SHA
    assert pushed_sha(_gitdir(tmp_path / "b", "", "loose")) == SHA


def test_the_report_words_green_and_red_and_the_exit_follows(tmp_path: Path) -> None:
    """GREEN exits 0, RED exits 1, and no replay yet is NONE."""
    green = tmp_path / "g"
    assert report(_gitdir(green, f"{SHA} 0 900\n", "packed")).startswith("GREEN")
    assert main(["--repo", str(green)]) == 0
    red = tmp_path / "r"
    _gitdir(red, f"{SHA} 2 300\n", "loose")
    assert main(["--repo", str(red)]) == 1
    assert report(_gitdir(tmp_path / "n", "", "packed")).startswith("NONE")


def test_a_replay_is_shipped_unshipped_or_refused(tmp_path: Path) -> None:
    """nemik:W604: the shipper's status beside the replay's, per sha."""
    gitdir = _gitdir(tmp_path / "s", f"{SHA} 0 900\n", "packed")
    assert shipped(gitdir, SHA).startswith("UNSHIPPED no shipper")
    (gitdir / "image-replica.shipped").write_text(f"{SHA} 0\n", encoding="utf-8")
    assert shipped(gitdir, SHA) == "SHIPPED"
    assert report(gitdir).endswith("[SHIPPED]")
    (gitdir / "image-replica.shipped").write_text(f"{SHA} 7\n", encoding="utf-8")
    assert shipped(gitdir, SHA) == "UNSHIPPED shipper exit 7"
    assert shipped(gitdir, "d" * 40).startswith("UNSHIPPED no shipper")
