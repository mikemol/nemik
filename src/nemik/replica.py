# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W592: read the image replica's result line and say what the queue writer should be told.

tools/image_replica_runner.sh (nemik:W590) records `<sha> <exit status> <seconds>` in
.git/image-replica.last after replaying the image's test stage on a pushed sha. A tick reads that
line and files the verdict through the writer (`--gate-red` or `--gate-green`); the background
process never writes the queue itself, so the single-writer lock holds. This module only parses and
words the verdict: it does no I/O, so a caller reads the file and passes the text in.
"""

FIELDS = 3  # sha, exit status, seconds


class Replay:
    """One recorded replay of the image's test stage."""

    sha: str
    status: int
    seconds: int

    def __init__(self, sha: str, status: int, seconds: int) -> None:
        """Hold the three recorded fields.

        Args:
            sha: The commit that was replayed.
            status: The replay's exit status; 0 means the stage passed.
            seconds: How long it took.

        """
        self.sha = sha
        self.status = status
        self.seconds = seconds


def parse(line: str) -> Replay:
    """Read one result line.

    Args:
        line: The text of .git/image-replica.last.

    Returns:
        The replay; its sha is empty when the line is empty or malformed (no Optional, which Codon
        spells differently from CPython).

    """
    fields = line.split()
    if len(fields) != FIELDS:
        return Replay("", 0, 0)
    if not (fields[1].lstrip("-").isdigit() and fields[2].isdigit()):
        return Replay("", 0, 0)
    return Replay(fields[0], int(fields[1]), int(fields[2]))


def verdict(replay: Replay, head: str) -> str:
    """Word what the tick should do about a replay.

    Args:
        replay: The parsed result; an empty sha means there is none.
        head: The sha that was pushed last.

    Returns:
        GREEN, RED, STALE (the result is for an older sha) or NONE, with the sha and the evidence.

    """
    if not replay.sha:
        return "NONE no replay recorded yet"
    short = replay.sha[:7]
    if replay.sha != head:
        return (
            f"STALE the last replay is of {short}, not {head[:7]}: a newer one is due"
        )
    if replay.status == 0:
        return f"GREEN {short} passed the image test stage in {replay.seconds} s"
    return (
        f"RED {short} failed the image test stage (exit {replay.status}, {replay.seconds} s): "
        "read .git/image-replica.log, then file --gate-red with the failing test"
    )
