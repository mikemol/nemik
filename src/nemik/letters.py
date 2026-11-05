# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W271 (gcalculus:W224), W277, W278, W282: every letter sits in its inbox and is owned.

The questions: is every letter in the inbox it is addressed to, and does a waypoint own it?

A letter is a file under `<repo>/inbox/`. Its first line says who wrote it and to whom
(`gcalculus → nemik: ...`, or with `->`). This reads the receiving side only: a letter whose header
names a recipient other than the inbox's owner is misdelivered, and one that names a repo that is
no workstream is unaddressable. A letter that was written and never put in any inbox cannot be seen
from here.

Operator direction 2026-10-10 (W275): a letter is the evidence of a waypoint in file form. So a
letter no waypoint in the fleet cites is an orphan. Each repo migrates its own inbox (W282): an
orphan is `stale` when its file name carries a date older than `--older-than` days (no waypoint ever
cited it, so it produced no work) or when everything it names in its own repo is closed; the rest
are `live`, and `--fold` prints the `--add` that gives each a waypoint and the `mv` that archives
the stale.

nemik:W1300: this module is the pure side and compiles under the pinned Codon: no subprocess, no
shutil, no keyword-only markers, no optional types (a sentinel stands for none) and no dataclass
or NamedTuple. What acts on the filesystem or the writer lives in nemik.check (`apply_letters`).
"""

import re
import time
from datetime import date
from pathlib import Path

from nemik.tracker import DICT, LIST, STR, Tree, parse_tree

_HEADER = re.compile(
    r"^(?:#\s*)?([A-Za-z0-9][\w.-]*)\s*(?:→|->)\s*([A-Za-z0-9][\w.-]*)\s*[:(]"
)
_REF = re.compile(r"\b([A-Za-z0-9][\w.-]*):W([1-9][0-9]*)\b")
_DATED = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")
_ALERT = re.compile(r"-alert-(.+)-(opened|resolved)-([0-9a-f]+)\.md$")

EPOCH_DAY = 719163  # date(1970, 1, 1).toordinal()
SECONDS_PER_DAY = 86400
NO_CUTOFF = -1  # no --older-than: no orphan is stale for its age
NO_AGE = -(1 << 31)  # a file name with no valid date has no age
NO_DAY = date(1970, 1, 1)  # no day given: today is read from the clock
PLAIN = 0  # report: the findings only
FOLD = 1  # report: and the commands that would fold the orphans
APPLY = 2  # report: the fold is carried out (by nemik.check)


class Letter:
    """One letter: the inbox it sits in, its file name, who wrote it and who it is addressed to."""

    inbox: str
    name: str
    sender: str
    recipient: str

    def __init__(self, inbox: str, name: str, sender: str, recipient: str) -> None:
        """Make a letter from its four facts."""
        self.inbox = inbox
        self.name = name
        self.sender = sender
        self.recipient = recipient

    def __eq__(self, other: object) -> bool:
        """Say whether another letter has the same four facts.

        Returns:
            True when `other` is a Letter with the same inbox, name, sender and recipient.

        """
        return (
            isinstance(other, Letter)
            and self.inbox == other.inbox
            and self.name == other.name
            and self.sender == other.sender
            and self.recipient == other.recipient
        )

    def __hash__(self) -> int:
        """Hash a letter by where it sits and its name, which equal letters share.

        Returns:
            The hash of `<inbox>/<name>`.

        """
        return hash(f"{self.inbox}/{self.name}")


def current_day() -> date:
    """Give today's date in UTC.

    Returns:
        The current UTC date.

    """
    return date.fromordinal(EPOCH_DAY + int(time.time()) // SECONDS_PER_DAY)


def quote(text: str) -> str:
    """Quote a word for a POSIX shell the way shlex.quote does.

    Returns:
        The word as is when it holds only safe characters, else in single quotes.

    """
    safe = all(c.isalnum() or c in "@%+=:,./-_" for c in text)
    if text and safe:
        return text
    return "'" + text.replace("'", "'\"'\"'") + "'"


def _first_line(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return next((ln.strip() for ln in text if ln.strip()), "")


def headers(root: Path) -> tuple[list[Letter], list[tuple[str, str]]]:
    """(addressed letters, [(inbox, file)] with no `from → to` header) under every `<repo>/inbox`.

    Returns:
        The addressed letters, and the (inbox, file name) of each letter with no header.

    """
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
    """One line per letter whose recipient is not the inbox it sits in, or is no workstream.

    Returns:
        One line per misdelivered letter, naming where it belongs or that its recipient
        is no workstream.

    """
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


def _load(path: Path) -> Tree:
    """Read a queue file as a parsed tree; an unreadable or unparseable one reads as empty.

    Returns:
        The queue's parsed tree; a tree holding only the null when the file cannot be read.

    Raises:
        TypeError: when the file parses to a value that is not an object, since the readers
            decide whether a letter is owned and a corrupt queue must not hide an orphan.

    """
    try:
        tree = parse_tree(path.read_text(encoding="utf-8"))
    except OSError:
        return Tree()
    except ValueError:
        return Tree()
    if tree.kinds[tree.root] != DICT:
        message = f"{path}: expected a queue object"
        raise TypeError(message)
    return tree


def _queue_text(tree: Tree) -> str:
    """Every string in a parsed queue, joined: a letter is cited if its file name appears in it.

    Returns:
        The strings, joined by newlines.

    """
    return "\n".join(
        tree.texts[at] for at in range(len(tree.kinds)) if tree.kinds[at] == STR
    )


def _closed(tree: Tree) -> set[str]:
    root = tree.root
    waypoints, residue = tree.get(root, "waypoints"), tree.get(root, "residue")
    cards = tree.kids[waypoints] if tree.kinds[waypoints] == LIST else []
    dropped = tree.kids[residue] if tree.kinds[residue] == LIST else []
    return {
        tree.string(one, "symbol")
        for one in cards
        if tree.string(one, "status") == "done"
    } | {tree.string(one, "symbol") for one in dropped}


def answered(repo: str, path: Path, tree: Tree) -> bool:
    """Say whether the letter names waypoints of `repo` and every one of them is closed.

    What it asked about has landed or been dropped. A letter naming none of `repo`'s waypoints is
    live.

    Returns:
        True when the letter names at least one of the repo's waypoints and all are closed.

    """
    own = {
        f"W{m[2]}"
        for m in _REF.finditer(path.read_text(encoding="utf-8", errors="replace"))
        if str(m[1]) == repo
    }
    return len(own) > 0 and own <= _closed(tree)


def age_days(path: Path, today: date) -> int:
    """Days since the date in the letter's file name (`YYYY-MM-DD-...`); NO_AGE when it has none.

    Returns:
        The age in whole days, or NO_AGE when the name has no date or the date is invalid.

    """
    m = _DATED.match(path.name)
    if not m:
        return NO_AGE
    year, month, day = int(m[1]), int(m[2]), int(m[3])
    try:
        return (today - date(year, month, day)).days
    except ValueError:
        return NO_AGE


def alert_key(path: Path) -> tuple[str, str, str]:
    """(alert name, opened|resolved, alert id) of a machine-generated alert letter, else empty.

    Returns:
        The alert name, its state and its id, or three empty strings when the file is not an
        alert letter.

    """
    m = _ALERT.search(path.name)
    return (m[1], m[2], m[3]) if m else ("", "", "")


def alert_closed(
    owner: str, path: Path, resolved: dict[tuple[str, str, str], str]
) -> bool:
    """nemik:W301 (substrate): an alert letter needs no card when its RESOLVED twin is present.

    A `resolved` letter is the end of the pair: nothing is left to act on. An `opened` letter is
    answered by construction when a `resolved` letter of the same alert name and id is dated the
    same day or later; an `opened` with none stays live. `resolved` maps (owner, name, id) to the
    latest resolved date (the file name's `YYYY-MM-DD`).

    Returns:
        True for a resolved letter, or an opened one whose resolved twin is dated the same
        day or later; False otherwise.

    """
    name, kind, ident = alert_key(path)
    if not kind:
        return False
    if kind == "resolved":
        return True
    return resolved.get((owner, name, ident), "") >= path.name[:10]


def orphans(root: Path, repo: str = "") -> list[tuple[str, Path, bool]]:
    """(repo, letter, answered) for each letter under `<repo>/inbox/` no waypoint cites.

    For `repo` alone when given.

    Returns:
        The (repo, letter path, answered) triples, in path order.

    """
    found: list[tuple[str, Path, bool]] = []
    # nemik:W280: a letter is owned when ANY waypoint in the fleet cites its path (a sender cites
    # `<repo>/inbox/<file>` in the waiting waypoint's evidence), or its own repo's queue names the
    # file.
    fleet = "\n".join(
        _queue_text(_load(state))
        for state in sorted(root.glob("*/.claude/paths-forward.json"))
    )
    resolved: dict[tuple[str, str, str], str] = {}
    for path in sorted(root.glob("*/inbox/*.md")):
        key = alert_key(path)
        if key[1] == "resolved":
            slot = (path.parents[1].name, key[0], key[2])
            resolved[slot] = max(resolved.get(slot, ""), path.name[:10])
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
            closed = answered(owner, path, queue) or alert_closed(owner, path, resolved)
            found.append((owner, path, closed))
    return found


def split_orphans(
    root: Path, repo: str, older_than: int, today: date
) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
    """(live, stale) orphans: stale is answered, or dated more than `older_than` days ago.

    Returns:
        The live and the stale orphans, each as (owner, path) pairs.

    """
    live: list[tuple[str, Path]] = []
    stale: list[tuple[str, Path]] = []
    for owner, path, closed in orphans(root, repo):
        age = age_days(path, today)
        old = older_than != NO_CUTOFF and age != NO_AGE and age > older_than
        if closed or old:
            stale.append((owner, path))
        else:
            live.append((owner, path))
    return live, stale


def fold_title(path: Path) -> str:
    """Give the title of the waypoint a live orphan letter becomes.

    Returns:
        `Answer <sender>: <the rest of the first line>`, or the first line when it has no header.

    """
    line = _first_line(path)
    head = _HEADER.match(line)
    if head:
        return f"Answer {head[1]}: {line[len(head[0]) :].strip()}"
    return line.lstrip("# ")


def fold_commands(
    root: Path,
    pf: str = "mikemol-paths-forward",
    repo: str = "",
    older_than: int = NO_CUTOFF,
    today: date = NO_DAY,
) -> list[str]:
    """One `--add` per live orphan letter: a waypoint in the recipient caused by the letter.

    Returns:
        The shell commands, one `--add` per live orphan.

    """
    day = current_day() if today == NO_DAY else today
    out: list[str] = []
    for owner, path in split_orphans(root, repo, older_than, day)[0]:
        state = root / owner / ".claude" / "paths-forward.json"
        out.append(
            f"{pf} --state {quote(str(state))} --add {quote(fold_title(path)[:140])} "
            f"--caused-by inbox/{path.name}"
        )
    return out


def archive_commands(
    root: Path,
    repo: str = "",
    older_than: int = NO_CUTOFF,
    today: date = NO_DAY,
) -> list[str]:
    """One `mv` per stale orphan, into that repo's `inbox/archive/`.

    Returns:
        The `mv` commands, one per stale orphan.

    """
    day = current_day() if today == NO_DAY else today
    return [
        f"mv {quote(str(path))} {quote(str(path.parent / 'archive'))}/"
        for _, path in split_orphans(root, repo, older_than, day)[1]
    ]


def held(root: Path, ltr: Letter) -> bool:
    """Say whether the letter's recipient holds it: in its inbox, or archived there.

    A repo that has read a letter files it under `inbox/archive/`, which is still delivered.

    Returns:
        True when the letter is in the recipient's inbox or its archive.

    """
    inbox = root / ltr.recipient / "inbox"
    return (inbox / ltr.name).exists() or (inbox / "archive" / ltr.name).exists()


def redeliveries(
    root: Path, workstreams: set[str], repo: str = ""
) -> list[tuple[Path, Path]]:
    """nemik:W310 (linux-sources, paperkit): (source, destination) for each misdelivered letter.

    The header names a workstream, and the result is a COPY into that workstream's `inbox/`, so the
    letter is delivered where it says and the sender keeps its copy (a waypoint there may cite
    it). Skips a letter the recipient already has. `repo` keeps those that sit in, or are
    addressed to, that repo.

    Returns:
        The (source, destination) pairs to copy.

    """
    addressed, _ = headers(root)
    out: list[tuple[Path, Path]] = []
    for ltr in addressed:
        if ltr.recipient == ltr.inbox or ltr.recipient not in workstreams:
            continue
        if repo and repo not in {ltr.inbox, ltr.recipient}:
            continue
        dest = root / ltr.recipient / "inbox" / ltr.name
        if dest.parent.is_dir() and not held(root, ltr):
            out.append((root / ltr.inbox / "inbox" / ltr.name, dest))
    return out


def report(
    root: Path,
    workstreams: set[str],
    mode: int = PLAIN,
    repo: str = "",
    older_than: int = NO_CUTOFF,
) -> tuple[list[str], int]:
    """Printable lines and the exit code: 0 clean, 5 when a letter is misdelivered.

    With mode FOLD, the live orphan letters are listed as `--add` commands and the stale ones as
    `mv` commands into inbox/archive (mode APPLY carries them out, in nemik.check, and lists
    nothing here). `repo` scopes the orphan listing AND the misdelivery lines to letters that sit
    in or are addressed to that repo; `older_than` makes a dated orphan stale after that many days.

    Returns:
        The lines to print and the exit code.

    """
    addressed, unaddressed = headers(root)
    if repo:
        addressed = [x for x in addressed if repo in {x.inbox, x.recipient}]

    # A misdelivered letter its recipient holds (in its inbox or archived there) is delivered
    # (W310). With APPLY the copies are made FIRST, so the verdict and the exit code are the after
    # state.
    delivery: list[str] = []
    if mode == FOLD:
        for src, dst in redeliveries(root, workstreams, repo):
            delivery.append(f"cp {src} {dst}")
    pending = [x for x in addressed if x.recipient == x.inbox or not held(root, x)]
    bad = misdelivered(pending, workstreams)
    lines = [
        f"letters: {len(addressed)} addressed, {len(unaddressed)} without a header"
    ]
    lines += [f"MISDELIVERED {row}" for row in bad]
    lines += delivery
    if mode == FOLD:
        add = fold_commands(root, repo=repo, older_than=older_than)
        move = archive_commands(root, repo=repo, older_than=older_than)
        lines.append(f"live orphans: {len(add)} (no waypoint cites them)")
        lines += add
        lines.append(f"stale orphans: {len(move)} (answered, or older than the cutoff)")
        lines += move
    return lines, 5 if bad else 0
