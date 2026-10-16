# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W590: the replica runner replays each sha once, records it, and runs single-flight."""

import fcntl
import shutil
from pathlib import Path

import installed

RUNNER = Path(__file__).resolve().parent.parent / "tools" / "image_replica_runner.sh"
GIT = shutil.which("git") or "git"
IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@t")


def _repo(tmp_path: Path) -> tuple[Path, str]:
    """Make a one-commit repository.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The repository path and its HEAD sha.

    """
    repo = tmp_path / "repo"
    repo.mkdir()
    installed.run(GIT, "init", "-q", "-b", "main", cwd=repo)
    installed.run(GIT, *IDENTITY, "commit", "-q", "--allow-empty", "-m", "x", cwd=repo)
    head = installed.run(GIT, "rev-parse", "HEAD", cwd=repo)
    return repo, head.stdout.strip()


def _stub(tmp_path: Path, status: int) -> Path:
    """Write a replica stub that logs its call and exits with a status.

    Args:
        tmp_path: A scratch directory.
        status: The exit status the stub reports.

    Returns:
        The stub path.

    """
    stub = tmp_path / "stub.sh"
    stub.write_text(
        f'#!/bin/sh\necho "$1" >> "{tmp_path}/calls"\necho "replay output of $1"\nexit {status}\n'
    )
    stub.chmod(0o755)
    return stub


def _calls(tmp_path: Path) -> list[str]:
    """Read the shas the stub was asked to replay.

    Args:
        tmp_path: The scratch directory.

    Returns:
        One sha per call.

    """
    path = tmp_path / "calls"
    return path.read_text().split() if path.exists() else []


def test_a_sha_is_replayed_once_and_its_result_recorded(tmp_path: Path) -> None:
    """The result line is sha, status, seconds; a second start finds the sha done."""
    repo, sha = _repo(tmp_path)
    stub = _stub(tmp_path, 3)
    for _ in range(2):
        run = installed.run(str(RUNNER), str(stub), "HEAD", "none", cwd=repo)
        assert run.returncode == 0
    assert _calls(tmp_path) == [sha]
    fields = (repo / ".git" / "image-replica.last").read_text().split()
    assert fields[:2] == [sha, "3"]


def test_a_held_lock_makes_a_second_start_exit_without_replaying(
    tmp_path: Path,
) -> None:
    """Single-flight: with the lock held elsewhere, the runner leaves at once."""
    repo, _ = _repo(tmp_path)
    with (repo / ".git" / "image-replica.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        stub = _stub(tmp_path, 0)
        run = installed.run(str(RUNNER), str(stub), "HEAD", "none", cwd=repo)
    assert run.returncode == 0
    assert _calls(tmp_path) == []


def test_the_replay_output_goes_to_the_shipper_and_the_replay_status_survives(
    tmp_path: Path,
) -> None:
    """nemik:W596: output reaches the shipper; its exit does not change the replay's."""
    repo, sha = _repo(tmp_path)
    shipper = tmp_path / "shipper.sh"
    shipper.write_text(
        f'#!/bin/sh\necho "args: $@" >> "{tmp_path}/shipped"\n'
        f'cat >> "{tmp_path}/shipped"\nexit 9\n'
    )
    shipper.chmod(0o755)
    command = f"{shipper} --field sha={{sha}}"
    run = installed.run(str(RUNNER), str(_stub(tmp_path, 4)), "HEAD", command, cwd=repo)
    assert run.returncode == 0
    shipped = (tmp_path / "shipped").read_text()
    assert f"args: --field sha={sha[:7]}" in shipped
    assert f"replay output of {sha}" in shipped
    assert (repo / ".git" / f"image-replica-{sha[:7]}.log").exists()
    assert (repo / ".git" / "image-replica.last").read_text().split()[:2] == [sha, "4"]
