"""nemik:W271 (gcalculus:W224), W277, W278, W282: is every letter in the inbox it is addressed to, and
does a waypoint own it?

A letter is a file under `<repo>/inbox/`. Its first line says who wrote it and to whom
(`gcalculus → nemik: ...`, or with `->`). This reads the receiving side only: a letter whose header
names a recipient other than the inbox's owner is misdelivered, and one that names a repo that is
no workstream is unaddressable. A letter that was written and never put in any inbox cannot be seen
from here.

Operator direction 2026-10-10 (W275): a letter is the evidence of a waypoint in file form. So a
letter no waypoint in the fleet cites is an orphan. Each repo migrates its own inbox (W282): an
orphan is `stale` when its file name carries a date older than `--older-than` days (no waypoint ever
cited it, so it produced no work) or when everything it names in its own repo is closed; the rest are
`live`, and `--fold` prints the `--add` that gives each a waypoint and the `mv` that archives the stale.
"""

from __future__ import annotations

import json
import re
import shlex
from datetime import UTC, date, datetime
from pathlib import Path
from typing import NamedTuple

_HEADER = re.compile(
    r"^(?:#\s*)?([A-Za-z0-9][\w.-]*)\s*(?:→|->)\s*([A-Za-z0-9][\w.-]*)\s*[:(]"
)
_REF = re.compile(r"\b([A-Za-z0-9][\w.-]*):W([1-9][0-9]*)\b")
_DATED = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")


class Letter(NamedTuple):
    inbox: str
    name: str
    sender: str
    recipient: str


def _today() -> date:
    return datetime.now(UTC).date()


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


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _queue_text(queue: dict) -> str:
    """Every string in a parsed queue, joined: a letter is cited if its file name appears in it."""
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

    walk(queue)
    return "\n".join(strings)


def _closed(queue: dict) -> set[str]:
    done = {
        w["symbol"] for w in queue.get("waypoints", []) if w.get("status") == "done"
    }
    return done | {r["symbol"] for r in queue.get("residue", [])}


def answered(repo: str, path: Path, queue: dict) -> bool:
    """True when the letter names waypoints of `repo` and every one of them is closed: what it
    asked about has landed or been dropped. A letter naming none of `repo`'s waypoints is live."""
    own = {
        f"W{m[2]}"
        for m in _REF.finditer(path.read_text(errors="replace"))
        if m[1] == repo
    }
    return bool(own) and own <= _closed(queue)


def age_days(path: Path, today: date) -> int | None:
    """Days since the date in the letter's file name (`YYYY-MM-DD-...`); None when it has none."""
    m = _DATED.match(path.name)
    if not m:
        return None
    try:
        return (today - date(int(m[1]), int(m[2]), int(m[3]))).days
    except ValueError:
        return None


def orphans(root: Path, repo: str | None = None) -> list[tuple[str, Path, bool]]:
    """(repo, letter, answered) for each letter under `<repo>/inbox/` no waypoint cites, for `repo`
    alone when given."""
    found: list[tuple[str, Path, bool]] = []
    # nemik:W280: a letter is owned when ANY waypoint in the fleet cites its path (a sender cites
    # `<repo>/inbox/<file>` in the waiting waypoint's evidence), or its own repo's queue names the file.
    fleet = "\n".join(
        _queue_text(_load(state))
        for state in sorted(root.glob("*/.claude/paths-forward.json"))
    )
    for path in sorted(root.glob("*/inbox/*.md")):
        owner = path.parents[1].name
        state = root / owner / ".claude" / "paths-forward.json"
        if (repo and owner != repo) or not state.exists():
            continue
        queue = _load(state)
        if (
            path.name not in _queue_text(queue)
            and f"{owner}/inbox/{path.name}" not in fleet
        ):
            found.append((owner, path, answered(owner, path, queue)))
    return found


def _split(
    root: Path, repo: str | None, older_than: int | None, today: date
) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
    """(live, stale) orphans: stale is answered, or dated more than `older_than` days ago."""
    live: list[tuple[str, Path]] = []
    stale: list[tuple[str, Path]] = []
    for owner, path, closed in orphans(root, repo):
        age = age_days(path, today)
        old = older_than is not None and age is not None and age > older_than
        (stale if closed or old else live).append((owner, path))
    return live, stale


def fold_commands(
    root: Path,
    pf: str = "mikemol-paths-forward",
    repo: str | None = None,
    older_than: int | None = None,
    today: date | None = None,
) -> list[str]:
    """One `--add` per live orphan letter: a waypoint in the recipient whose caused_by is the letter."""
    out: list[str] = []
    for owner, path in _split(root, repo, older_than, today or _today())[0]:
        line = _first_line(path)
        head = _HEADER.match(line)
        if head:
            title = f"Answer {head[1]}: {line[len(head[0]) :].strip()}"
        else:
            title = line.lstrip("# ")
        state = root / owner / ".claude" / "paths-forward.json"
        out.append(
            f"{pf} --state {shlex.quote(str(state))} --add {shlex.quote(title[:140])} "
            f"--caused-by inbox/{path.name}"
        )
    return out


def archive_commands(
    root: Path,
    repo: str | None = None,
    older_than: int | None = None,
    today: date | None = None,
) -> list[str]:
    """One `mv` per stale orphan, into that repo's `inbox/archive/`."""
    return [
        f"mv {shlex.quote(str(path))} {shlex.quote(str(path.parent / 'archive'))}/"
        for _, path in _split(root, repo, older_than, today or _today())[1]
    ]


def report(
    root: Path,
    workstreams: set[str],
    fold: bool = False,
    repo: str | None = None,
    older_than: int | None = None,
) -> tuple[list[str], int]:
    """Printable lines and the exit code: 0 clean, 5 when a letter is misdelivered.

    With `fold`, the live orphan letters are listed as `--add` commands and the stale ones as `mv`
    commands into inbox/archive (neither changes the code; nothing is applied). `repo` scopes the
    orphan listing to one inbox, `older_than` makes a dated orphan stale after that many days.
    """
    addressed, unaddressed = headers(root)
    bad = misdelivered(addressed, workstreams)
    lines = [
        f"letters: {len(addressed)} addressed, {len(unaddressed)} without a header"
    ]
    lines += [f"MISDELIVERED {row}" for row in bad]
    if fold:
        add = fold_commands(root, repo=repo, older_than=older_than)
        move = archive_commands(root, repo=repo, older_than=older_than)
        lines.append(f"live orphans: {len(add)} (no waypoint cites them)")
        lines += add
        lines.append(f"stale orphans: {len(move)} (answered, or older than the cutoff)")
        lines += move
    return lines, 5 if bad else 0
