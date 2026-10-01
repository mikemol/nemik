"""nemik:W128: the operator's asks as iCalendar VTODOs (RFC 5545), one projection with two sinks.

`nemik-ics` writes the projection to a local .ics file that Akonadi (or any calendar) can subscribe
to (life:W23); nemik:W121 writes the same VTODOs into the Google Tasks collection. Only asks that
need the operator ("needs-you", nemik-operator's list) are projected.

Privacy (life:W23, operator 2026-09-28): queues carry personal text, so this runs host-side only,
never in nemik-serve or the export, and only for repos listed in the opt-in file
(~/.config/nemik/ics.toml: `repos = ["life", ...]`, or `["*"]` for all). No file: nothing is written.

Decide/act comes from the blocked_on prefix `operator: decide|act`, the same rule nemik-operator
and mtools:W277 use, so the three never disagree. Time fields (DUE, VALARM, RRULE ...) pass through
DTSTART and DUE pass through from mtools:W300 (nemik:W134); VALARM and RRULE follow when mtools:W278/W279 land.
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
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545 3.1: lines over 75 octets continue on the next line after CRLF + one space."""
    raw = line.encode()
    if len(raw) <= 75:
        return line
    out, cur = [], b""
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
            return m[1].lower(), part[m.end():].strip(" :—-")
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
        lines += [prop for name, key in (("DTSTART", "dtstart"), ("DUE", "due"))
                  if (prop := time_property(name, a.get(key, "")))]
        lines += [f"RELATED-TO;RELTYPE=CHILD:{uid(w)}" for w in a.get("waiting", [])]
        if link:
            lines.append(f"URL:{link.rstrip('/')}/#{a['ref']}")
        lines.append("END:VTODO")
        out.append(lines)
    return out


def calendar(todos: list[list[str]]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "X-WR-CALNAME:nemik: needs you"]
    for t in todos:
        lines += t
    lines.append("END:VCALENDAR")
    return "".join(_fold(line) + "\r\n" for line in lines)


def feed(root: Path, opt_in: Path, link: str = "") -> str:
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
    return calendar(vtodos(operator_asks(g), opted_in(opt_in), link))


DEFAULT_HELPER = Path.home() / "github" / "nemik" / "build" / "akonadi-tasks" / "nemik-akonadi-tasks"


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

    ap = argparse.ArgumentParser(prog="nemik-tasks", description=(tasks_main.__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github, or the export layout root")
    ap.add_argument("--opt-in", type=Path, default=DEFAULT_OPT_IN, help="TOML with repos = [...]")
    ap.add_argument("--link", default="", help="base URL of the nemik view, for each task's URL")
    ap.add_argument("--helper", type=Path, default=DEFAULT_HELPER, help="the nemik-akonadi-tasks binary")
    ap.add_argument("--list", required=True, help="the Google Tasks list, by name")
    ap.add_argument("--create-list", action="store_true", help="create the list when none has that name")
    ap.add_argument("--apply", action="store_true", help="write; without it, only print the plan")
    args = ap.parse_args(argv)
    if not args.helper.exists():
        print(f"ERROR: {args.helper} is missing; build it with ./setup.sh", flush=True)
        raise SystemExit(2)
    try:
        text = feed(args.root, args.opt_in, args.link)
    except Exception as e:  # noqa: BLE001 - any feed failure is the 2 of the exit contract
        print(f"ERROR: feed: {e}", flush=True)
        raise SystemExit(2) from e
    cmd = [str(args.helper), "--list", args.list]
    cmd += ["--create-list"] * args.create_list + ["--apply"] * args.apply
    sys.stdout.flush()
    raise SystemExit(subprocess.run(cmd, input=text.encode(), check=False).returncode)


def main(argv: list[str] | None = None) -> None:
    """nemik-ics: the operator's needs-you asks, from opted-in repos, as an iCalendar file of VTODOs."""
    import argparse

    from nemik.check import default_root

    ap = argparse.ArgumentParser(prog="nemik-ics", description=(main.__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github, or the export layout root")
    ap.add_argument("--opt-in", type=Path, default=DEFAULT_OPT_IN, help="TOML with repos = [...]")
    ap.add_argument("--link", default="", help="base URL of the nemik view, for each task's URL")
    ap.add_argument("--out", type=Path, help="write here (atomically) instead of stdout")
    args = ap.parse_args(argv)

    text = feed(args.root, args.opt_in, args.link)
    if args.out is None:
        print(text, end="")
        return
    tmp = args.out.with_suffix(args.out.suffix + ".tmp")
    tmp.write_text(text, newline="")
    tmp.replace(args.out)  # a subscriber never reads a half-written file
