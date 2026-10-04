"""nemik:W157/W113: the operator's calendars, read host-side as event occurrences.

For each configured collection the KF6 Akonadi helper (W147) exports one .ics into a private temp
directory (0700, the file 0600); mtools' `mikemol-ics` (W157 step 1, lossless) expands it to
per-occurrence records over a window; the file is deleted before returning. The Google credential
never leaves KWallet, the event text never goes to the export, metrics or nemik-serve (operator
2026-09-28), and nothing here prints an event.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

from nemik.vtodo import DEFAULT_HELPER

DEFAULT_CONFIG = Path.home() / ".config" / "nemik" / "calendars.toml"
_LABEL = re.compile(r"[a-z][a-z0-9-]{0,31}")


class Calendar(NamedTuple):
    """One opted-in calendar: its Akonadi collection and an optional summary filter (nemik:W190)."""
    name: str
    include: tuple[str, ...] = ()


def load_calendars(path: Path = DEFAULT_CONFIG) -> dict[str, Calendar]:
    """nemik:W158/W190: which calendars nemik may read, as {label: Calendar}.

    ~/.config/nemik/calendars.toml:

        [calendars]
        home = "Personal"          # label = what a waypoint cites as cal:home/<uid>
        chores = { name = "Chores", include = ["Mike", "Supper: Pascal"] }

    `include` (life:W31, operator 2026-10-02) keeps only events whose SUMMARY contains one of the
    patterns: case-sensitive substrings, any pattern matching. Absent or empty means everything.
    No file reads no calendar: the operator opts each one in, as with ics.toml. A label must be
    short lowercase (it appears in refs). A bad entry or an unknown key fails rather than being
    skipped: a typo'd `includes` would otherwise silently mean "no filter".
    """
    import tomllib

    if not path.exists():
        return {}
    cals = tomllib.loads(path.read_text()).get("calendars", {})
    if not isinstance(cals, dict):
        raise ValueError(f"{path}: [calendars] must be a table of label = \"collection name\"")
    out: dict[str, Calendar] = {}
    for label, spec in cals.items():
        bad = f"{path}: bad entry {label!r}: "
        if not _LABEL.fullmatch(label):
            raise ValueError(bad + "labels are [a-z][a-z0-9-]*")
        if isinstance(spec, str):
            spec = {"name": spec}
        if not isinstance(spec, dict) or set(spec) - {"name", "include"}:
            raise ValueError(bad + "a name string, or a table with only `name` and `include`")
        name, include = spec.get("name"), spec.get("include", [])
        if not isinstance(name, str) or not name:
            raise ValueError(bad + "`name` must be a non-empty string")
        if not isinstance(include, list) or not all(isinstance(x, str) and x for x in include):
            raise ValueError(bad + "`include` must be a list of non-empty strings")
        out[label] = Calendar(name, tuple(include))
    return dict(sorted(out.items()))


def load_collections(path: Path = DEFAULT_CONFIG) -> dict[str, str]:
    """{label: Akonadi collection name}: load_calendars without the filters (nemik:W158)."""
    return {label: c.name for label, c in load_calendars(path).items()}


KEEP = ("uid", "start", "end", "all_day", "summary", "recurrence_id")


def _venv_ics() -> str:
    """mikemol-ics from nemik's own venv (it is vendored there, nemik:W157), not from PATH: a host
    caller runs .venv/bin/nemik-days without activating the venv (life-82, 2026-10-02)."""
    import sys

    return str(Path(sys.executable).parent / "mikemol-ics")


def occurrences(collections: dict[str, str], *, start: str, window: str = "14d",
                helper: Path = DEFAULT_HELPER, ics: str | None = None,
                includes: dict[str, tuple[str, ...]] | None = None,
                stats: dict[str, tuple[int, int]] | None = None) -> list[dict]:
    """[{label, uid, start, end, all_day, summary, recurrence_id}] for every collection, by start.

    `collections` maps a short label (what waypoints cite as cal:<label>/<uid>) to the Akonadi
    collection name. A collection that fails to export or parse raises: a silent gap would read as
    a free day. `includes` filters a label's events to those whose summary contains a pattern
    (nemik:W190); `stats`, when given, is filled with {label: (matched, total)} for every label, so
    a filter that matches nothing is reported as "0 of N", never as a free day.
    """
    ics = ics or _venv_ics()
    if not Path(ics).exists() and not shutil.which(ics):
        raise FileNotFoundError(f"the calendar reader {ics} is missing: rebuild nemik's venv (bazel build //:.venv)")
    tmp = Path(tempfile.mkdtemp(prefix="nemik-cal-"))  # mkdtemp is 0700
    try:
        out: list[dict] = []
        for label, name in sorted(collections.items()):
            f = tmp / f"{label}.ics"
            subprocess.run([str(helper), "--export-calendar", name, "--out", str(f)],
                           check=True, capture_output=True)
            text = subprocess.run([ics, "--from", start, "--window", window, "--json", str(f)],
                                  check=True, capture_output=True, text=True).stdout
            pats = (includes or {}).get(label, ())
            total = matched = 0
            for line in text.splitlines():
                rec = json.loads(line)
                if rec.get("kind") != "occurrence":
                    continue
                total += 1
                if pats and not any(p in (rec.get("summary") or "") for p in pats):
                    continue
                matched += 1
                out.append({"label": label, **{k: rec.get(k) for k in KEEP}})
            if stats is not None:
                stats[label] = (matched, total)
            f.unlink()
        return sorted(out, key=lambda r: (r["start"] or "", r["label"], r["uid"] or ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def dedupe(rows: list[dict]) -> list[dict]:
    """nemik:W191 (life-82): one row per (start, summary) across DIFFERENT calendars.

    The household and main calendars repeat some entries (same chore, same instant). The first
    calendar's row stays and names the others in `also`; their waiters are merged in, so a waypoint
    citing either copy still shows. Two identical entries inside ONE calendar are two real events
    and both stay: only a calendar not yet represented under that key is merged. Display only: the
    event graph keeps every occurrence, so cal:<label>/<uid> refs still resolve to their own copy.
    """
    out: list[dict] = []
    first: dict[tuple, dict] = {}
    for r in rows:
        k = (r["start"], r["summary"])
        p = first.get(k)
        if p is None:
            first[k] = r = dict(r)
            out.append(r)
        elif r["label"] != p["label"] and r["label"] not in p.get("also", []):
            p["also"] = [*p.get("also", []), r["label"]]
            p["waiting"] = sorted({*p.get("waiting", []), *r.get("waiting", [])})
        else:
            out.append(dict(r))  # a second event in a calendar already represented: a real one
    return out


CAL_REF = re.compile(r"cal:([a-z][a-z0-9-]{0,31})/(\S+)")


def event_graph(occs: list[dict], queues):
    """nemik:W159: occurrences as nemik:Event nodes, and every open waypoint whose blocked_on cites
    `cal:<label>/<uid>` waiting for that event's next occurrence (nemik:waitsFor).

    HOST-SIDE ONLY: the result carries event text, so it is merged into a graph for nemik-operator
    on the host, never into nemik-serve, the export or metrics (operator 2026-09-28).
    """
    from rdflib import Graph, Literal, URIRef
    from rdflib.namespace import DCTERMS, RDF

    from nemik.adapter import NEMIK, OSLC_CM

    g = Graph()
    nxt: dict[tuple[str, str], URIRef] = {}
    for o in occs:  # sorted by start, so the first seen per (label, uid) is the next occurrence
        ev = URIRef(f"urn:nemik:cal:{o['label']}/{o['uid']}/{o['recurrence_id'] or o['start']}")
        g.add((ev, RDF.type, NEMIK.Event))
        g.add((ev, DCTERMS.title, Literal(o["summary"] or "")))
        g.add((ev, NEMIK.dtstart, Literal(o["start"] or "")))
        nxt.setdefault((o["label"], o["uid"]), ev)
    for n, _, text in queues.triples((None, NEMIK.blockedOn, None)):
        if (n, OSLC_CM.state, NEMIK.Done) in queues:
            continue
        if (m := CAL_REF.fullmatch(str(text).strip())) and (ev := nxt.get((m[1], m[2]))):
            g.add((n, NEMIK.waitsFor, ev))
    return g


def days_main(argv: list[str] | None = None, g=None) -> None:
    """nemik-days: the next N days of the operator's opted-in calendars, each with its waiters.

    A separate command, not a flag on nemik-operator (nemik:W161): nemik-serve runs nemik-operator
    for its Tools panel, so anything nemik-operator can reach is on the served path. This module is
    reachable from no served module (tests/test_calendar_boundary.py).
    """
    import argparse
    from datetime import date

    from rdflib import Graph

    from nemik.blocks import ref
    from nemik.adapter import NEMIK
    from nemik.check import default_root, survey
    from nemik.vtodo import DEFAULT_HELPER

    ap = argparse.ArgumentParser(prog="nemik-days", description=(days_main.__doc__ or "").splitlines()[0])
    ap.add_argument("days", type=int, nargs="?", default=7, help="how many days ahead (default 7)")
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github")
    ap.add_argument("--calendars", type=Path, default=DEFAULT_CONFIG, help="calendars.toml")
    ap.add_argument("--helper", type=Path, default=DEFAULT_HELPER, help="the nemik-akonadi-tasks binary")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-dedupe", action="store_true",
                    help="list every calendar's copy of an entry that repeats across calendars (nemik:W191)")
    args = ap.parse_args(argv)
    cals = load_calendars(args.calendars)
    cols = {label: c.name for label, c in cals.items()}
    if not cols:
        print(f"no calendar opted in ({args.calendars})")
        return
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    try:
        stats: dict[str, tuple[int, int]] = {}
        occs = occurrences(cols, start=date.today().isoformat(), window=f"{args.days}d", helper=args.helper,
                           includes={label: c.include for label, c in cals.items() if c.include}, stats=stats)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        raise SystemExit(2) from e
    except subprocess.CalledProcessError as e:
        # The helper refuses (nemik:W193) when Akonadi is not running; say what it said, not a traceback.
        why = ((e.stdout or b"").decode(errors="replace").strip() or (e.stderr or b"").decode(errors="replace").strip()
               or f"exit {e.returncode}")
        print(f"ERROR: the calendar export failed: {why.splitlines()[-1]}")
        raise SystemExit(2) from e
    eg = event_graph(occs, g)
    rows = []
    for o in occs:
        ev = f"urn:nemik:cal:{o['label']}/{o['uid']}/{o['recurrence_id'] or o['start']}"
        rows.append({**o, "waiting": sorted(ref(n) for n, _, t in eg.triples((None, NEMIK.waitsFor, None)) if str(t) == ev)})
    if not args.no_dedupe:
        rows = dedupe(rows)
    # nemik:W190: a filtered calendar reports what its filter kept. "0 of N matched" says the filter
    # ate the day, not that the day is free.
    report = [f"filter {label}: {stats[label][0]} of {stats[label][1]} matched"
              + (" (nothing matched: that is the filter, not a free day)" if stats[label][0] == 0 and stats[label][1] else "")
              for label, c in cals.items() if c.include and label in stats]
    if args.json:
        print(json.dumps(rows, indent=2))  # the row list, unchanged for existing readers
        for line in report:
            print(line, file=sys.stderr)
        return
    print(f"next {args.days} days ({len(rows)})")
    for d in rows:
        waits = f"  <- {', '.join(d['waiting'])}" if d["waiting"] else ""
        also = f"  [also: {', '.join(d['also'])}]" if d.get("also") else ""
        print(f"  {(d['start'] or '')[:16]:16} {d['label']:10} {(d['summary'] or '')[:60]}{also}{waits}")
    for line in report:
        print(f"  {line}")
