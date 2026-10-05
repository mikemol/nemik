"""nemik:W128: the operator's asks as iCalendar VTODOs (RFC 5545), one projection with two sinks.

`nemik-ics` writes the projection to a local .ics file that Akonadi (or any calendar) can subscribe
to (life:W23); nemik:W121 writes the same VTODOs into the Google Tasks collection. Only asks that
need the operator ("needs-you", nemik-operator's list) are projected.

Privacy (life:W23, operator 2026-09-28): queues carry personal text, so this runs host-side only,
never in nemik-serve or the export, and only for repos listed in the opt-in file
(~/.config/nemik/ics.toml: `repos = ["life", ...]`, or `["*"]` for all). No file: nothing is written.

Decide/act comes from the blocked_on prefix `operator: decide|act`, the same rule nemik-operator
and mtools:W277 use, so the three never disagree. Time fields (DUE, VALARM, RRULE ...) pass through
DTSTART and DUE pass through from mtools:W300 (nemik:W134); VALARMs pass through from mtools:W279 (nemik:W129); RRULE follows mtools:W278.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from nemik.blocks import EXPLICIT

PRODID = "-//nemik//operator asks//EN"
DEFAULT_OPT_IN = Path.home() / ".config" / "nemik" / "ics.toml"


class _Every(set):
    """`repos = ["*"]`: every repo (operator 2026-09-30: "All repos")."""

    def __contains__(self, _repo: object) -> bool:
        return True


def opted_in(path: Path) -> set[str]:
    """Repos whose asks may be projected. A missing file opts nobody in; "*" opts every repo in."""
    if not path.exists():
        return set()
    repos = set(tomllib.loads(path.read_text()).get("repos", []))
    return _Every() if "*" in repos else repos


def uid(ref: str) -> str:
    return f"nemik:{ref}"


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """RFC 5545 3.1: lines over 75 octets continue on the next line after CRLF + one space."""
    raw = line.encode()
    if len(raw) <= 75:
        return line
    out: list[str] = []
    cur = b""
    for ch in line:
        b = ch.encode()
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode())
            cur = b""
        cur += b
    out.append(cur.decode())
    return "\r\n ".join(out)


def _stamp(iso: str) -> str:
    """An ISO-8601 UTC ledger stamp as an iCalendar DATE-TIME; the epoch when there is none, so
    the output depends only on the queues, never on when it ran (nemik:W119)."""
    digits = re.sub(r"[^0-9]", "", iso)[:14]
    return f"{digits[:8]}T{digits[8:14]}Z" if len(digits) == 14 else "19700101T000000Z"


def time_property(name: str, value: str) -> str:
    """An mtools:W300 value as an RFC 5545 property line, or "" when there is none (nemik:W134).

    mtools stores the value as written: DATE `20261001`, UTC `20261001T203000Z`, or
    `TZID=Zone/Name:20261001T163000` (floating times are refused at write, so none arrive here).
    """
    if not value:
        return ""
    if value.startswith("TZID="):
        tz, _, local = value.partition(":")
        return f"{name};{tz}:{local}"
    if re.fullmatch(r"\d{8}", value):
        return f"{name};VALUE=DATE:{value}"
    return f"{name}:{value}"


def stated_ask(ask: str) -> tuple[str, str]:
    """(verb, what) from an ask that may join several blocked_on values with ' | '."""
    for part in ask.split(" | "):
        if m := EXPLICIT.match(part):
            return m[1].lower(), part[m.end() :].strip(" :—-")
    return "decide", ask


def vtodos(asks: list[dict], repos: set[str], link: str = "") -> list[list[str]]:
    """One VTODO (as property lines) per needs-you ask from an opted-in repo, in ref order."""
    out = []
    for a in sorted(asks, key=lambda a: a["ref"]):
        repo = a["ref"].partition(":")[0]
        if a["category"] != "needs-you" or repo not in repos:
            continue
        verb, what = stated_ask(a["ask"])
        desc = [f"{a['ref']}: {a['title']}", f"operator: {verb} {what}"]
        if a.get("waiting"):
            desc.append("waiting behind this: " + ", ".join(a["waiting"]))
        if a.get("same_ask"):
            desc.append("same ask as: " + ", ".join(a["same_ask"]))
        lines = [
            "BEGIN:VTODO",
            f"UID:{uid(a['ref'])}",
            f"DTSTAMP:{_stamp(a.get('last_activity', ''))}",
            f"SUMMARY:{_escape(f'{verb}: {what}')}",
            f"DESCRIPTION:{_escape(chr(10).join(desc))}",
            "STATUS:NEEDS-ACTION",
            f"CATEGORIES:nemik,{_escape(repo)}",
        ]
        # The waypoints this ask releases, as RFC 5545 relations (RELTYPE=CHILD: they follow it).
        lines += [
            prop
            for name, key in (("DTSTART", "dtstart"), ("DUE", "due"))
            if (prop := time_property(name, a.get(key, "")))
        ]
        # mtools:W309: recurrence rides along as stored (nemik:W145 expands it for firing).
        if a.get("rrule"):
            lines.append(f"RRULE:{a['rrule']}")
            lines += [time_property("EXDATE", x) for x in a.get("exdates", [])]
        lines += [f"RELATED-TO;RELTYPE=CHILD:{uid(w)}" for w in a.get("waiting", [])]
        if link:
            lines.append(f"URL:{link.rstrip('/')}/#{a['ref']}")
        # mtools:W279: each alarm as a display VALARM, its TRIGGER exactly as stored (nemik:W129).
        for trig in a.get("alarms", []):
            lines += [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_escape(f'{verb}: {what}')}",
                f"TRIGGER;{trig}"
                if trig.startswith(("RELATED=", "VALUE="))
                else f"TRIGGER:{trig}",
                "END:VALARM",
            ]
        lines.append("END:VTODO")
        out.append(lines)
    return out


def grouped(todos: list[list[str]]) -> list[list[str]]:
    """nemik:W163 (W148): one parent VTODO per repo, each ask its subtask (RELATED-TO;RELTYPE=PARENT).

    The parent's UID is nemik:repo:<repo> (the Tasks helper keys it as ref `repo:<repo>`), its
    summary `<repo> (<n asks>)`, its DUE the earliest child DUE, as stored. Children keep their
    UIDs and dates, so an existing task is re-parented in place, not recreated. A repo whose last
    ask closes drops out of the feed and the helper completes its parent like any closed ask.
    """
    by_repo: dict[str, list[list[str]]] = {}
    for t in todos:
        repo = next(line for line in t if line.startswith("CATEGORIES:")).split(",", 1)[
            1
        ]
        by_repo.setdefault(repo.replace("\\,", ","), []).append(t)
    out = []
    for repo, kids in sorted(by_repo.items()):
        dues = [line for k in kids for line in k if line.startswith("DUE")]
        parent = [
            "BEGIN:VTODO",
            f"UID:nemik:repo:{repo}",
            "DTSTAMP:19700101T000000Z",
            f"SUMMARY:{_escape(f'{repo} ({len(kids)})')}",
            f"DESCRIPTION:{_escape(f'nemik: asks from {repo}')}",
            "STATUS:NEEDS-ACTION",
            f"CATEGORIES:nemik,{_escape(repo)}",
        ]
        if dues:  # earliest by the date-time digits, whatever the value form
            parent.append(
                min(
                    dues,
                    key=lambda d: re.sub(r"[^0-9]", "", d.rpartition(":")[2]).ljust(
                        15, "0"
                    ),
                )
            )
        out.append(parent + ["END:VTODO"])
        out += [
            k[:-1] + [f"RELATED-TO;RELTYPE=PARENT:nemik:repo:{repo}", k[-1]]
            for k in kids
        ]
    return out


def calendar(todos: list[list[str]]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "X-WR-CALNAME:nemik: needs you",
    ]
    for t in todos:
        lines += t
    lines.append("END:VCALENDAR")
    return "".join(_fold(line) + "\r\n" for line in lines)


def feed(root: Path, opt_in: Path, link: str = "", group: bool = False) -> str:
    """The iCalendar text nemik-ics prints, built in-process."""
    from rdflib import Graph

    from nemik.adapter import ledger_graph
    from nemik.blocks import operator_asks
    from nemik.check import LEDGER, survey, workstream_files

    g = Graph()
    for _, qg, _ in survey(root):
        if qg is not None:
            g += qg
    for repo, path in workstream_files(root, LEDGER):
        g += ledger_graph(repo, path)[0]
    todos = vtodos(operator_asks(g), opted_in(opt_in), link)
    return calendar(grouped(todos) if group else todos)


DEFAULT_HELPER = (
    Path.home() / "github" / "nemik" / "build" / "akonadi-tasks" / "nemik-akonadi-tasks"
)


def tasks_main(argv: list[str] | None = None) -> None:
    """nemik-tasks: sync the operator's needs-you asks into a Google Tasks list (via Akonadi).

    One entry point for luthen's timer (luthen-observability:W234: no authored shell, so no pipe in
    ExecStart). The feed is built in-process; the KF6 Akonadi helper (a host build, ./setup.sh) gets
    it on stdin. Its stdout (CREATE/UPDATE/COMPLETE/DONE-CLAIM lines) passes through, and its exit
    code is returned: 0 ok, 1 some writes failed, 2 no unique list or Akonadi unreachable. A missing
    helper or a failed feed is also 2.
    """
    import argparse
    import subprocess
    import sys

    from nemik.check import default_root

    ap = argparse.ArgumentParser(
        prog="nemik-tasks", description=(tasks_main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument(
        "--opt-in", type=Path, default=DEFAULT_OPT_IN, help="TOML with repos = [...]"
    )
    ap.add_argument(
        "--link", default="", help="base URL of the nemik view, for each task's URL"
    )
    ap.add_argument(
        "--helper",
        type=Path,
        default=DEFAULT_HELPER,
        help="the nemik-akonadi-tasks binary",
    )
    ap.add_argument("--list", required=True, help="the Google Tasks list, by name")
    ap.add_argument(
        "--create-list",
        action="store_true",
        help="create the list when none has that name",
    )
    ap.add_argument(
        "--apply", action="store_true", help="write; without it, only print the plan"
    )
    ap.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="REF",
        help="sync only this repo:W<n> (repeatable); other tasks are left untouched (nemik:W162)",
    )
    ap.add_argument(
        "--flat",
        action="store_true",
        help="one task per ask, no per-repo parent (default: a parent task per repo, nemik:W148/W163)",
    )
    ap.add_argument(
        "--retry-wait",
        type=int,
        default=25,
        metavar="SECONDS",
        help="with --apply, rerun while the helper defers a child's parent, waiting this long for the "
        "Google resource to sync (at most 3 reruns; nemik:W148)",
    )
    args = ap.parse_args(argv)
    if not args.helper.exists():
        print(f"ERROR: {args.helper} is missing; build it with ./setup.sh", flush=True)
        raise SystemExit(2)
    try:
        text = feed(args.root, args.opt_in, args.link, not args.flat)
    except Exception as e:
        print(f"ERROR: feed: {e}", flush=True)
        raise SystemExit(2) from e
    cmd = [str(args.helper), "--list", args.list]
    cmd += ["--create-list"] * args.create_list + ["--apply"] * args.apply
    for r in args.only:
        cmd += ["--only", r]
    sys.stdout.flush()
    # nemik:W148: a child can only name its parent by Google's own task id, which exists once the
    # Google resource has uploaded the parent. The first apply creates parents and the helper prints
    # DEFER-PARENT for children it could not attach yet; wait for the sync and rerun, so one
    # invocation converges (the timer would otherwise need two ticks).
    import time

    tries = 1 + (3 if args.apply and not args.flat else 0)
    for attempt in range(tries):
        run = subprocess.run(cmd, input=text.encode(), capture_output=True, check=False)
        sys.stdout.write(run.stdout.decode(errors="replace"))
        sys.stderr.write(run.stderr.decode(errors="replace"))
        sys.stdout.flush()
        if (
            run.returncode != 0
            or b"DEFER-PARENT" not in run.stdout
            or attempt == tries - 1
        ):
            break
        print(
            f"RETRY {attempt + 1}: parents are not on Google yet; waiting {args.retry_wait}s for the resource to sync",
            flush=True,
        )
        time.sleep(args.retry_wait)
    raise SystemExit(run.returncode)


def main(argv: list[str] | None = None) -> None:
    """nemik-ics: the operator's needs-you asks, from opted-in repos, as an iCalendar file of VTODOs."""
    import argparse

    from nemik.check import default_root

    ap = argparse.ArgumentParser(
        prog="nemik-ics", description=(main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument(
        "--opt-in", type=Path, default=DEFAULT_OPT_IN, help="TOML with repos = [...]"
    )
    ap.add_argument(
        "--link", default="", help="base URL of the nemik view, for each task's URL"
    )
    ap.add_argument(
        "--out", type=Path, help="write here (atomically) instead of stdout"
    )
    args = ap.parse_args(argv)

    text = feed(args.root, args.opt_in, args.link)
    if args.out is None:
        print(text, end="")
        return
    tmp = args.out.with_suffix(args.out.suffix + ".tmp")
    tmp.write_text(text, newline="")
    tmp.replace(args.out)  # a subscriber never reads a half-written file
