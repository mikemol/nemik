# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W594: nemik-replica, the image replica's verdict for the pushed sha.

Reads `.git/image-replica.last` (written by tools/image_replica_runner.sh, nemik:W590) and the sha
`origin/main` points at, and prints nemik.replica.verdict. A tick runs it and files `--gate-red` or
`--gate-green` through the queue writer from what it says; this command only reads.
"""

import argparse
import sys
from pathlib import Path

from nemik.replica import parse, verdict

REMOTE_REF = "refs/remotes/origin/main"


def pushed_sha(gitdir: Path) -> str:
    """Find the sha origin/main points at, loose or packed.

    Args:
        gitdir: The repository's .git directory.

    Returns:
        The sha, or an empty string when the ref is unknown.

    """
    loose = gitdir / REMOTE_REF
    if loose.exists():
        return loose.read_text(encoding="utf-8").strip()
    packed = gitdir / "packed-refs"
    if packed.exists():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.endswith(f" {REMOTE_REF}"):
                return line.split()[0]
    return ""


def report(gitdir: Path) -> str:
    """Word the verdict for a repository.

    Args:
        gitdir: The repository's .git directory.

    Returns:
        The verdict line.

    """
    last = gitdir / "image-replica.last"
    text = last.read_text(encoding="utf-8") if last.exists() else ""
    replay = parse(text)
    return f"{verdict(replay, pushed_sha(gitdir))} [{shipped(gitdir, replay.sha)}]"


def shipped(gitdir: Path, sha: str) -> str:
    """Say whether a replay's lines reached the log service (nemik:W604).

    Args:
        gitdir: The repository's .git directory.
        sha: The replayed commit.

    Returns:
        SHIPPED, or UNSHIPPED with the shipper's exit status or the reason there is none.

    """
    record = gitdir / "image-replica.shipped"
    fields = record.read_text(encoding="utf-8").split() if record.exists() else []
    if len(fields) != len(["sha", "status"]) or fields[0] != sha:
        return "UNSHIPPED no shipper ran for this sha"
    return "SHIPPED" if fields[1] == "0" else f"UNSHIPPED shipper exit {fields[1]}"


def main(argv: list[str] | None = None) -> int:
    """Print the verdict; exit 1 when the replay is RED.

    Args:
        argv: The arguments, or None for the process's own.

    Returns:
        The exit status.

    """
    ap = argparse.ArgumentParser(
        prog="nemik-replica", description=(main.__doc__ or "").strip()
    )
    ap.add_argument("--repo", type=Path, default=Path.cwd(), help="the repository root")
    args = ap.parse_args(argv)
    repo: Path = args.repo
    line = report(repo / ".git")
    sys.stdout.write(line + "\n")
    return 1 if line.startswith("RED") else 0
