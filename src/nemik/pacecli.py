# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1107: `nemik-rank --pace`, the ratchets that are behind, one line each, for a tick's hook.

The pace run writes ratchet-pace.json into the export tree (pacepublish reads it for the gauges).
Nothing printed which ratchets are behind, so a session lost them in prose and the ratchets went
unsupervised for 13 hours (github-8f, 2026-10-26). This prints one line per behind ratchet and
exits 1 when any repo is behind, 0 when none is, and 2 when the file cannot be read, so a dark
sensor is loud as well. Read-only.
"""

import sys
from pathlib import Path

from nemik.pacepublish import BEHIND, PACE_FILE, UNKNOWN, read_pace

EXPORT_TREE = Path.home() / ".local" / "share" / "luthen" / "nemik-export"
BEHIND_EXIT = 1
UNREADABLE_EXIT = 2


def pace_lines(text: str) -> list[str]:
    """Word the behind rows of a pace file, one line each.

    Args:
        text: The pace file's text.

    Returns:
        A line per behind ratchet (repo, ratchet, the fall observed over the window, the fall
        required, and when the pace was computed); a line per unknown one, since an unread
        ratchet is not a paid one; empty when none is behind or unknown. A file that is not a
        pace file is refused by read_pace with ValueError.

    """
    as_of, window, rows = read_pace(text)
    lines: list[str] = []
    for repo, ratchet, state, seen, owed in rows:
        if state == BEHIND:
            lines.append(
                f"behind {repo} {ratchet}: fell {seen} over {window} landings, owes {owed} "
                f"(pace of {as_of})"
            )
        elif state == UNKNOWN:
            lines.append(f"unknown {repo} {ratchet}: no verdict (pace of {as_of})")
    return lines


def pace_exit(words: list[str]) -> int:
    """Answer a command line that asks for --pace, before any survey is built.

    Read from the plain words, not the parsed namespace, so the check costs nothing and adds no
    untyped attribute to the ranking command.

    Args:
        words: The command line's arguments (not the program name). Without --root the pace file
            is read from luthen's export tree, where it is published.

    Returns:
        show_pace's exit code when --pace is among the arguments, else -1.

    """
    if "--pace" not in words:
        return -1
    at = words.index("--root") + 1 if "--root" in words else 0
    return show_pace(Path(words[at]) if 0 < at < len(words) else EXPORT_TREE)


def pace_process() -> int:
    """Answer the process's own command line when it asks for --pace.

    Returns:
        pace_exit's answer over the arguments the process was started with.

    """
    return pace_exit(sys.argv[1:])


def show_pace(root: Path) -> int:
    """Print the behind rows of the fleet's pace file and say by the exit code whether any exist.

    Args:
        root: The export tree that holds ratchet-pace.json.

    Returns:
        1 when a ratchet is behind or unknown, 0 when none is, 2 when the file is missing or not a
        pace file.

    """
    try:
        lines = pace_lines((root / PACE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.stdout.write(f"pace unreadable: {e}\n")
        return UNREADABLE_EXIT
    if lines:
        sys.stdout.write("\n".join(lines) + "\n")
        return BEHIND_EXIT
    sys.stdout.write("no ratchet is behind\n")
    return 0
