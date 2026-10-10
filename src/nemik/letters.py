"""nemik:W271 (gcalculus:W224), W277: is every letter in the inbox it is addressed to, and does a
waypoint own it?

A letter is a file under `<repo>/inbox/`. Its first line says who wrote it and to whom
(`gcalculus → nemik: ...`, or with `->`). This reads the receiving side only: a letter whose header
names a recipient other than the inbox's owner is misdelivered, and one that names a repo that is
no workstream is unaddressable. A letter that was written and never put in any inbox cannot be seen
from here.

Operator direction 2026-10-10 (W275): a letter is the evidence of a waypoint in file form. So a
letter no waypoint of its repo cites (by file name, in `caused_by` or any text field) is an orphan,
and `--fold` prints the `--add` that gives it a waypoint.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import NamedTuple

_HEADER = re.compile(
    r"^(?:#\s*)?([A-Za-z0-9][\w.-]*)\s*(?:→|->)\s*([A-Za-z0-9][\w.-]*)\s*[:(]"
)


class Letter(NamedTuple):
    inbox: str
    name: str
    sender: str
    recipient: str


def _first_line(path: Path) -> str:
    text = path.read_text(errors="replace").splitlines()
    return next((ln.strip() for ln in text if ln.strip()), "")


def headers(root: Path) -> tuple[list[Letter], list[tuple[str, str]]]:
    """(addressed letters, [(inbox, file)] with no `from → to` header) under every `<repo>/inbox`."""
    addressed: list[Letter] = []
    unaddressed: list[tuple[str, str]] = []
    for path in sorted(root.glob("*/inbox/*.md")):
        inbox = path.parents[1].name
        found = _HEADER.match(_first_line(path))
        if found:
            addressed.append(Letter(inbox, path.name, found[1], found[2]))
        else:
            unaddressed.append((inbox, path.name))
    return addressed, unaddressed


def misdelivered(letters: list[Letter], workstreams: set[str]) -> list[str]:
    """One line per letter whose recipient is not the inbox it sits in, or is no workstream."""
    out: list[str] = []
    for ltr in letters:
        if ltr.recipient != ltr.inbox:
            where = (
                f"belongs in {ltr.recipient}/inbox"
                if ltr.recipient in workstreams
                else f"names {ltr.recipient}, which is no workstream"
            )
            out.append(f"{ltr.inbox}/inbox/{ltr.name}: from {ltr.sender}; {where}")
    return out


def _queue_text(path: Path) -> str:
    """Every string in a repo's queue, joined: a letter is cited if its file name appears in it."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return ""
    strings: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, str):
            strings.append(node)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for item in node.values():
                walk(item)

    walk(data)
    return "\n".join(strings)


def orphans(root: Path) -> list[tuple[str, Path]]:
    """(repo, letter) for each letter under `<repo>/inbox/` that no waypoint of `repo` cites."""
    found: list[tuple[str, Path]] = []
    for path in sorted(root.glob("*/inbox/*.md")):
        repo = path.parents[1].name
        queue = root / repo / ".claude" / "paths-forward.json"
        if queue.exists() and path.name not in _queue_text(queue):
            found.append((repo, path))
    return found


def fold_commands(root: Path, pf: str = "mikemol-paths-forward") -> list[str]:
    """One `--add` per orphan letter: a waypoint in the recipient whose caused_by is the letter."""
    out: list[str] = []
    for repo, path in orphans(root):
        line = _first_line(path)
        head = _HEADER.match(line)
        if head:
            title = f"Answer {head[1]}: {line[len(head[0]) :].strip()}"
        else:
            title = line.lstrip("# ")
        state = root / repo / ".claude" / "paths-forward.json"
        out.append(
            f"{pf} --state {shlex.quote(str(state))} --add {shlex.quote(title[:140])} "
            f"--caused-by inbox/{path.name}"
        )
    return out


def report(
    root: Path, workstreams: set[str], fold: bool = False
) -> tuple[list[str], int]:
    """Printable lines and the exit code: 0 clean, 5 when a letter is misdelivered.

    With `fold`, the orphan letters are listed as `--add` commands (and do not change the code).
    """
    addressed, unaddressed = headers(root)
    bad = misdelivered(addressed, workstreams)
    lines = [
        f"letters: {len(addressed)} addressed, {len(unaddressed)} without a header"
    ]
    lines += [f"MISDELIVERED {row}" for row in bad]
    if fold:
        cmds = fold_commands(root)
        lines.append(f"orphans: {len(cmds)} letters no waypoint cites")
        lines += cmds
    return lines, 5 if bad else 0
