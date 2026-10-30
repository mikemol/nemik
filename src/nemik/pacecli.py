# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1107: `nemik-rank --pace`, the ratchets that are behind, one line each, for a tick's hook.

The pace run writes ratchet-pace.json into the export tree (pacepublish reads it for the gauges).
Nothing printed which ratchets are behind, so a session lost them in prose and the ratchets went
unsupervised for 13 hours (github-8f, 2026-10-26). This prints one line per behind ratchet and
exits 1 when any repo is behind, 0 when none is, and 2 when the file cannot be read, so a dark
sensor is loud as well. Read-only.

nemik:W1284: a pace is a reading at a time. When the command names a repo, the header gives the
pace's as_of beside the repo's newest landing (the last ref update of its main branch, read from
the plain-text reflog, so this module needs no git and stays inside the Codon census), and every
ratchet line is marked PENDING while the pace is older than that landing: a reading that predates
the work it judges does not classify it (host standing 12).
"""

import sys
from pathlib import Path

from nemik.pacepublish import BEHIND, OK, PACE_FILE, UNKNOWN, read_extras, read_pace

EXPORT_TREE = Path.home() / ".local" / "share" / "luthen" / "nemik-export"
BEHIND_EXIT = 1
UNREADABLE_EXIT = 2
NEVER = 1 << 62  # sorts a ratchet that is not falling after every finite horizon
REFLOG = ".git/logs/refs/heads/main"  # one line per ref update
DAY = 86400
EPOCH_DAYS = 719468  # days from 0000-03-01 to 1970-01-01, the civil-calendar offset
ERA_DAYS = 146097  # days in a 400-year era
STAMP_LENGTH = 20  # YYYY-MM-DDTHH:MM:SSZ
MARCH = 3
WRAP = 10  # the March-based month index (Jan, Feb) that belongs to the next civil year


def epoch_of(stamp: str) -> int:
    """Read an ISO UTC stamp (`YYYY-MM-DDTHH:MM:SSZ`) as epoch seconds.

    Returns:
        The epoch seconds, or 0 when the text is not such a stamp.

    """
    if len(stamp) != STAMP_LENGTH or stamp[10] != "T" or not stamp.endswith("Z"):
        return 0
    try:
        year, month, day = int(stamp[0:4]), int(stamp[5:7]), int(stamp[8:10])
        hour, minute, second = int(stamp[11:13]), int(stamp[14:16]), int(stamp[17:19])
    except ValueError:
        return 0
    year -= 1 if month < MARCH else 0
    era = year // 400
    yoe = year - era * 400
    doy = (153 * (month + (-3 if month >= MARCH else 9)) + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    days = era * ERA_DAYS + doe - EPOCH_DAYS
    return days * DAY + hour * 3600 + minute * 60 + second


def iso_of(epoch: int) -> str:
    """Write epoch seconds as an ISO UTC stamp (`YYYY-MM-DDTHH:MM:SSZ`).

    Returns:
        The stamp.

    """
    days, rest = divmod(epoch, DAY)
    z = days + EPOCH_DAYS
    era = z // ERA_DAYS
    doe = z - era * ERA_DAYS
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    day = doy - (153 * mp + 2) // 5 + 1
    month = mp + (3 if mp < WRAP else -9)
    year = yoe + era * 400 + (1 if month < MARCH else 0)
    hour, rest = divmod(rest, 3600)
    minute, second = divmod(rest, 60)
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"


def newest_landing(repo_dir: Path) -> int:
    """Read when a repo's main branch last moved, from its plain-text reflog.

    Each reflog line ends `<author> <epoch> <zone><tab><message>`; the last line is the newest
    ref update, which for a gated repo is its newest landing. No git is run.

    Returns:
        The epoch seconds, or 0 when the reflog is missing, empty or not in that shape.

    """
    try:
        lines = (repo_dir / REFLOG).read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    if not lines:
        return 0
    words = lines[-1].split("\t")[0].split()
    try:
        return int(words[-2])
    except (IndexError, ValueError):
        return 0


def _reach(extras: dict[str, tuple[int, int]], repo: str, ratchet: str) -> str:
    """Word a ratchet's value and landings to zero (nemik:W1115).

    Returns:
        The words, empty when the pace file states none for the ratchet; no fall is worded as no
        way to reach zero while the value is above zero.

    """
    got = extras.get(f"{repo}\n{ratchet}")
    if got is None:
        return ""
    value, landings = got
    if landings < 0:
        return f"; {value} left, no fall to reach zero"
    return f"; {value} left, {landings} landings to zero"


def pace_lines(text: str) -> list[str]:
    """Word the behind rows of a pace file, one line each.

    Args:
        text: The pace file's text.

    Returns:
        A line per behind ratchet (repo, ratchet, the fall observed over the window, the fall
        required, the value left and landings to zero when the file states them, and when the pace
        was computed); a line per unknown one, since an unread ratchet is not a paid one; empty
        when none is behind or unknown. A file that is not a pace file is refused by read_pace
        with ValueError.

    """
    as_of, window, rows = read_pace(text)
    extras = read_extras(text)
    lines: list[str] = []
    for repo, ratchet, state, seen, owed in rows:
        if state == BEHIND:
            lines.append(
                f"behind {repo} {ratchet}: fell {seen} over {window} landings, owes {owed}"
                f"{_reach(extras, repo, ratchet)} (pace of {as_of})"
            )
        elif state == UNKNOWN:
            lines.append(f"unknown {repo} {ratchet}: no verdict (pace of {as_of})")
    return lines


def horizon_lines(text: str) -> list[str]:
    """Word the ratchets that are not behind but still hold a value, with their horizon.

    Not behind is not falling fast enough: it reads ok while thousands of landings from zero.

    Args:
        text: The pace file's text.

    Returns:
        A line per ok ratchet that states a value above zero, longest horizon first; empty when
        the file states none.

    """
    _, _, rows = read_pace(text)
    extras = read_extras(text)
    slow: list[tuple[int, str, str]] = []
    for repo, ratchet, state, _, _ in rows:
        value, landings = extras.get(f"{repo}\n{ratchet}", (0, 0))
        if state == OK and value > 0:
            slow.append((landings if landings >= 0 else NEVER, repo, ratchet))
    slow.sort(reverse=True)
    return [
        f"ok {repo} {ratchet}{_reach(extras, repo, ratchet)}"
        for _, repo, ratchet in slow
    ]


def behind_files(repo: str) -> list[str]:
    """Name the ratchet files a repo is behind on, as the tags its paydown cards carry (W993).

    A list, not a frozenset or a tuple: Codon has no frozenset and takes no `tuple[str, ...]`, and
    this module is held to the census.

    Args:
        repo: The repo whose cards are being ranked.

    Returns:
        `file:<ratchet>` for each of the repo's behind rows in the export tree's pace file; empty
        when the file is missing or unreadable, since a dark sensor must not reorder the queue
        (it is loud elsewhere: --pace exits 2 and nemik_ratchet_pace_readable is 0).

    """
    try:
        _, _, rows = read_pace((EXPORT_TREE / PACE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [
        f"file:{ratchet}"
        for name, ratchet, state, _, _ in rows
        if name == repo and state == BEHIND
    ]


def _repo_in(words: list[str]) -> str:
    """Find the repo a --pace command line names: its first word that is not an option.

    Returns:
        The repo name, or "" when the line names none (the value after --root is not a repo).

    """
    skip = words.index("--root") + 1 if "--root" in words else -1
    for at, word in enumerate(words):
        if word and not word.startswith("-") and at != skip:
            return word
    return ""


def pace_exit(words: list[str]) -> int:
    """Answer a command line that asks for --pace, before any survey is built.

    Read from the plain words, not the parsed namespace, so the check costs nothing and adds no
    untyped attribute to the ranking command.

    Args:
        words: The command line's arguments (not the program name). Without --root the pace file
            is read from luthen's export tree, where it is published. A repo named among them
            adds the newest-landing header and the PENDING marks (nemik:W1284).

    Returns:
        show_pace's exit code when --pace is among the arguments, else -1.

    """
    if "--pace" not in words:
        return -1
    at = words.index("--root") + 1 if "--root" in words else 0
    root = Path(words[at]) if 0 < at < len(words) else EXPORT_TREE
    repo = _repo_in(words)
    landed = newest_landing(Path.home() / "github" / repo) if repo else 0
    return show_pace(root, landed, repo)


def pace_process() -> int:
    """Answer the process's own command line when it asks for --pace.

    Returns:
        pace_exit's answer over the arguments the process was started with.

    """
    return pace_exit(sys.argv[1:])


def _marked(line: str, repo: str) -> str:
    """Mark a pace line PENDING when it judges `repo`, the repo whose landing postdates the pace.

    A line about another repo is left alone: this repo's landing says nothing about whether the
    pace of that repo's ratchets is stale. The all-clear line judges the named repo too.

    Returns:
        The line, with PENDING in front when it is about `repo`.

    """
    words = line.split()
    about = words[1] if len(words) > 1 else ""
    return f"PENDING {line}" if about == repo or line.startswith("no ratchet") else line


def show_pace(root: Path, landed: int = 0, repo: str = "") -> int:
    """Print the behind rows of the fleet's pace file and say by the exit code whether any exist.

    Args:
        root: The export tree that holds ratchet-pace.json.
        landed: Epoch seconds of the repo's newest landing, or 0 when none is known. With it the
            output starts with the pace's as_of beside that landing, and every ratchet line is
            marked PENDING while the pace is older than the landing.
        repo: The repo the landing belongs to, for the header.

    Returns:
        1 when a ratchet is behind or unknown, 0 when none is, 2 when the file is missing or not a
        pace file.

    """
    try:
        text = (root / PACE_FILE).read_text(encoding="utf-8")
        lines = pace_lines(text)
        slow = horizon_lines(text)
        as_of = read_pace(text)[0]
    except (OSError, ValueError) as e:
        sys.stdout.write(f"pace unreadable: {e}\n")
        return UNREADABLE_EXIT
    shown = (lines or ["no ratchet is behind"]) + slow
    if landed:
        pending = epoch_of(as_of) < landed
        head = f"pace of {as_of}; newest landing of {repo} {iso_of(landed)}"
        shown = [head + (": PENDING" if pending else ": current"), *shown]
        if pending:
            shown = [shown[0], *[_marked(line, repo) for line in shown[1:]]]
    sys.stdout.write("\n".join(shown) + "\n")
    return BEHIND_EXIT if lines else 0
