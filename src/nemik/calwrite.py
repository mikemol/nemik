"""nemik:W197 (life's ask): open dated waypoints as VEVENTs, for writing into a calendar.

A waypoint with a DTSTART or a DUE (mtools:W300), and optionally alarms (W279) and a recurrence
(W309/W310), becomes one event whose UID is `nemik:<repo>:W<n>`: stable, so a republish updates the
event instead of duplicating it, and the UID prefix is how nemik tells its own events from the
operator's. A done or dropped waypoint is simply absent from the feed, and the writer removes the
event it left behind. A completed occurrence of a recurring waypoint becomes an EXDATE.

Which repos are written is the operator's opt-in (`mirror` in calendars.toml), never implied. This
module only builds the text; the Akonadi helper writes it (nemik:W198), and nothing here runs
without being asked. HOST-SIDE ONLY, like nemik.calendars: the feed carries waypoint titles.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import DCTERMS, RDF

from nemik.adapter import BASE, NEMIK, OSLC_CM
from nemik.calendars import DEFAULT_CONFIG, load_calendars
from nemik.check import default_root, survey
from nemik.vtodo import DEFAULT_HELPER, _escape, _fold, time_property

PRODID = "-//nemik//dated waypoints//EN"
OWNED = "nemik:"  # a UID with this prefix is nemik's own event, in any calendar
_DATE = re.compile(r"\d{8}")


def uid(ref: str) -> str:
    return f"{OWNED}{ref}"


def _is_date(value: str) -> bool:
    return bool(_DATE.fullmatch(value))


def _zone(value: str) -> str:
    """What must match for two time values to be compared: a TZID, UTC, or neither (a DATE)."""
    if value.startswith("TZID="):
        return value.partition(":")[0]
    return "Z" if value.endswith("Z") else ""


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value.rpartition(":")[2])


def _next_day(value: str) -> str:
    """A DATE value (YYYYMMDD) one day later: an all-day event's end is exclusive."""
    d = date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:]}") + timedelta(days=1)
    return d.strftime("%Y%m%d")


def event_times(dtstart: str, due: str, needs_end: bool) -> tuple[str, str]:
    """(DTSTART, DTEND) values as mtools stores them; DTEND is "" when the event has none.

    With both, the event runs from the start to the due (an all-day due is inclusive, so the end is
    the next day). With only a due, the event sits at the deadline. A DTEND is also made up when an
    alarm is relative to the END and the event would otherwise have none, since such a trigger has
    nothing to count from. Mixed kinds (a DATE with a date-time, or two zones) get no end rather
    than a wrong one.
    """
    start = dtstart or due
    end = ""
    if (
        dtstart
        and due
        and _is_date(start) == _is_date(due)
        and _zone(start) == _zone(due)
    ):
        if _is_date(due):
            end = _next_day(due) if due > start else ""
        elif _digits(due) >= _digits(start):
            end = due
    elif needs_end and not _is_date(start):
        end = start
    return start, end


def _alarm_lines(trigger: str, summary: str) -> list[str]:
    head = (
        f"TRIGGER;{trigger}"
        if trigger.startswith(("RELATED=", "VALUE="))
        else f"TRIGGER:{trigger}"
    )
    return [
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{summary}",
        head,
        "END:VALARM",
    ]


def event_lines(
    ref: str,
    title: str,
    dtstart: str,
    due: str,
    alarms: Iterable[str] = (),
    rrule: str = "",
    exdates: Iterable[str] = (),
) -> list[str]:
    """One VEVENT as property lines. DTSTAMP is fixed so the feed depends only on the queues."""
    triggers = sorted(alarms)
    start, end = event_times(
        dtstart, due, any(t.startswith("RELATED=END") for t in triggers)
    )
    summary = _escape(title)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid(ref)}",
        "DTSTAMP:19700101T000000Z",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{_escape(f'nemik-ref: {ref}')}",
        time_property("DTSTART", start),
    ]
    if end:
        lines.append(time_property("DTEND", end))
    if rrule:
        lines.append(f"RRULE:{rrule}")
        lines += [time_property("EXDATE", x) for x in sorted(set(exdates))]
    for trigger in triggers:
        lines += _alarm_lines(trigger, summary)
    lines.append("END:VEVENT")
    return lines


def events(g: Graph, repos: Iterable[str]) -> list[list[str]]:
    """One VEVENT per open dated waypoint of `repos`, in repo then waypoint order."""
    want = set(repos)
    found: list[tuple[str, int, list[str]]] = []
    for n in set(g.subjects(NEMIK.workstream, None)):
        repo = str(n).removeprefix(BASE).partition("/")[0]
        symbol = str(g.value(n, NEMIK.symbol) or "")
        if repo not in want or not symbol:
            continue
        if (n, RDF.type, NEMIK.Dropped) in g or (n, OSLC_CM.state, NEMIK.Done) in g:
            continue
        dtstart = str(g.value(n, NEMIK.dtstart) or "")
        due = str(g.value(n, NEMIK.due) or "")
        if not (dtstart or due):
            continue
        rrule = str(g.value(n, NEMIK.rrule) or "")
        gone = {str(x) for x in g.objects(n, NEMIK.exdate)}
        gone |= {str(x) for x in g.objects(n, NEMIK.occurrenceDone)}
        lines = event_lines(
            f"{repo}:{symbol}",
            str(g.value(n, DCTERMS.title) or symbol),
            dtstart,
            due,
            (str(a) for a in g.objects(n, NEMIK.alarm)),
            rrule,
            gone,
        )
        found.append((repo, int(symbol.lstrip("W") or 0), lines))
    return [lines for _, _, lines in sorted(found, key=lambda f: f[:2])]


def feed(g: Graph, repos: Iterable[str]) -> str:
    """The iCalendar text the Akonadi helper reads on stdin (CRLF, folded at 75 octets)."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}"]
    for event in events(g, repos):
        lines += event
    lines.append("END:VCALENDAR")
    return "".join(_fold(line) + "\r\n" for line in lines)


def _write(helper: Path, name: str, text: str, apply: bool) -> tuple[int, str]:
    """Run the Akonadi helper's --write-calendar on one calendar; (exit code, its output)."""
    cmd = [str(helper), "--write-calendar", name]
    if apply:
        cmd.append("--apply")
    run = subprocess.run(cmd, input=text.encode(), capture_output=True, check=False)
    return run.returncode, run.stdout.decode(errors="replace")


def main(argv: list[str] | None = None, g: Graph | None = None) -> int:
    """nemik-calendar-write: dated waypoints of opted-in repos, written into opted-in calendars.

    Reads ~/.config/nemik/calendars.toml: a calendar with `write = true` and `mirror = [repos]`
    gets one event per open dated waypoint of those repos (nemik.calwrite), upserted by UID, and
    loses the events of waypoints that are done or no longer dated. Plans unless --apply. Exit 0 ok,
    1 some writes failed, 2 refused (no write rights on the calendar, Akonadi not running).
    """
    ap = argparse.ArgumentParser(
        prog="nemik-calendar-write", description=(main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github")
    ap.add_argument(
        "--calendars", type=Path, default=DEFAULT_CONFIG, help="calendars.toml"
    )
    ap.add_argument(
        "--helper",
        type=Path,
        default=DEFAULT_HELPER,
        help="the nemik-akonadi-tasks binary",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="write; without it only the plan is printed",
    )
    args = ap.parse_args(argv)
    targets = {
        label: c for label, c in load_calendars(args.calendars).items() if c.write
    }
    if not targets:
        print(
            f"no calendar opted in for writing ({args.calendars}: write = true, mirror = [repos])"
        )
        return 0
    if not args.helper.exists():
        print(f"ERROR: {args.helper} is missing; build it with ./setup.sh")
        return 2
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    worst = 0
    for label, cal in targets.items():
        code, out = _write(args.helper, cal.name, feed(g, cal.mirror), args.apply)
        print(
            f"== {label}: {len(events(g, cal.mirror))} dated waypoints of {', '.join(cal.mirror)}"
        )
        print(out, end="")
        worst = max(worst, code)
    return worst
