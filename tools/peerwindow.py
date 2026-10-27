# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1149: is a peer tree quiet, and did what was handed to it get placed.

linux-sources' peer_write_window.py answered a question two of its cards were waiting on without
anyone scheduled to ask it: a blocker on someone else's tree holds a hand-set re-check date, and a
date makes the question askable, it does not say whether the blocker still holds. This reads the
other tree every run. For each WATCHED peer it counts the tracked changes, the files both staged
and unstaged (`MM`, a peer mid-operation on that exact path, counted apart from a plain ` M`) and
the untracked ones; for each HANDED artefact it asks git whether the peer's HEAD lists it, because
a file in a working tree is not one another party can fetch.

It reports facts and never permission: a quiet tree is true of one instant. The watched peers and
the handed artefacts are data (tools/peer-watch.json), not code, so a card that waits on a peer's
tree names it there.

    python3 tools/peerwindow.py [ROOT]
"""

import sys
from pathlib import Path

from nemik.check import default_root
from nemik.history import git_lines
from nemik.tracker import parse_tree

WATCH = Path(__file__).with_name("peer-watch.json")
Pair = tuple[str, str]
Counts = tuple[int, int, int]


def read_watch(text: str) -> tuple[list[Pair], list[Pair]]:
    """Read the watch list.

    Args:
        text: peer-watch.json's text: {"watched": [{peer, why}], "handed": [{peer, path}]}.

    Returns:
        (each watched peer with why it is watched, each handed artefact as peer and path).

    """
    tree = parse_tree(text)
    root = tree.root
    watched = [
        (tree.string(item, "peer"), tree.string(item, "why"))
        for item in tree.kids[tree.get(root, "watched")]
    ]
    handed = [
        (tree.string(item, "peer"), tree.string(item, "path"))
        for item in tree.kids[tree.get(root, "handed")]
    ]
    return watched, handed


def counts_of(lines: list[str]) -> Counts:
    """Count the lines of `git status --porcelain` by what they say.

    Returns:
        (tracked changes, both staged and unstaged, untracked). MM is the sharp case: a plain
        modified file is merely uncommitted, but one staged and unstaged at once is a peer in the
        middle of an operation on that path.

    """
    untracked = sum(1 for line in lines if line.startswith("??"))
    both = sum(
        1
        for line in lines
        if len(line) > 1 and " " not in line[:2] and not line.startswith("?")
    )
    return len(lines) - untracked, both, untracked


def churn(repo: Path) -> Counts | None:
    """Count a peer tree's changes.

    Returns:
        The three counts; None when the directory is not a git tree here or git cannot answer.

    """
    if not (repo / ".git").exists():
        return None
    lines = git_lines(repo, "status", "--porcelain")
    return None if lines is None else counts_of(lines)


def unplaced(root: Path, handed: list[Pair]) -> list[Pair]:
    """Name the handed artefacts a peer's HEAD does not list.

    Returns:
        Each (peer, path) handed over and absent from that peer's HEAD; a peer that is not a git
        tree here is skipped, as it cannot be asked.

    """
    out: list[Pair] = []
    for peer, path in handed:
        repo = root / peer
        if not (repo / ".git").exists():
            continue
        tracked = git_lines(repo, "ls-tree", "-r", "--name-only", "HEAD")
        if path not in (tracked or []):
            out.append((peer, path))
    return out


def report(watched: list[tuple[Pair, Counts | None]], missing: list[Pair]) -> list[str]:
    """Write each watched peer's churn, then every handoff not placed, then the totals.

    Args:
        watched: Each (peer, why) with its counts, or None when it could not be read.
        missing: The handed artefacts absent from their peer's HEAD.

    Returns:
        The lines, in the order linux-sources' tool printed them.

    """
    lines: list[str] = []
    for (peer, why), counts in watched:
        if counts is None:
            lines.append(f"  UNAVAILABLE  {peer} — not a git tree here; NOT measured")
        else:
            tracked, both, untracked = counts
            state = "QUIET" if tracked == 0 else "BUSY "
            lines.append(
                f"  {state}  {peer}: {tracked} tracked change(s), {both} staged+unstaged, "
                f"{untracked} untracked"
            )
        lines.append(f"          {why}")
    lines.extend(
        f"  UNPLACED  {peer}:{path} — handed over, absent from HEAD"
        for peer, path in missing
    )
    lines.append(
        f"peer_write_window: {len(watched)} watched peer(s), {len(missing)} unplaced handoff(s)"
    )
    return lines


def main(argv: list[str]) -> int:
    """Print the watched peers' churn and the unplaced handoffs.

    Returns:
        0.

    """
    root = Path(argv[0]) if argv else default_root()
    watched, handed = read_watch(WATCH.read_text(encoding="utf-8"))
    read = [((peer, why), churn(root / peer)) for peer, why in watched]
    sys.stdout.write("\n".join(report(read, unplaced(root, handed))) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
