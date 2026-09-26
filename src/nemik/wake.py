"""nemik-wake: which blocked-on entities must be awake, and which are not.

Joins what is waiting on each workstream (nemik.blocks.inbound: other repos' open waypoints
blocked on it) with whether that workstream has a live session, read from luthen's
`loop_liveness` JSON. nemik does not detect liveness itself.

Awake states, from loop_liveness's verdict:
    asleep     no live session (verdict "dormant"): wake it
    idle       a live session whose loop is not ticking (stale / disarmed / unknown / future)
    awake      a live session ticking ("ok")
    unknown    no liveness reading for this repo

Liveness source, first found: --liveness FILE ('-' for stdin); <root>/liveness.json (the export
luthen writes for the pod); luthen-observability's own `python -m checks.loop_liveness`, run
through its venv, when that tree exists beside the root.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph

from nemik.blocks import inbound, operator_asks

REWAKE_S = 30 * 60  # matches luthen checks/waker.py's own default

AWAKE = {"ok": "awake", "dormant": "asleep"}


def read_liveness(root: Path, source: str | None) -> tuple[dict, str]:
    """Return ({repo: record}, where it came from); ({}, reason) when there is none."""
    try:
        if source == "-":
            return json.load(sys.stdin)["repos"], "stdin"
        if source:
            return json.loads(Path(source).read_text())["repos"], source
        export = root / "liveness.json"
        if export.exists():
            return json.loads(export.read_text())["repos"], str(export)
        luthen = root / "luthen-observability"
        py = luthen / ".venv" / "bin" / "python"
        if py.exists():
            out = subprocess.run(
                [str(py), "-m", "checks.loop_liveness"], cwd=luthen, capture_output=True, text=True, check=True
            ).stdout
            return json.loads(out)["repos"], "luthen-observability checks.loop_liveness"
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        return {}, f"unreadable: {exc}"
    return {}, "no liveness source"


def age_seconds(last_tick: str | None, now: datetime | None = None) -> float | None:
    """Seconds between an ISO-8601 `last_tick` and `now` (default: real now); None if unusable.

    A caller gets an age, not a raw timestamp it has to subtract itself -- the gap luthen's W117
    named (nemik:W18).
    """
    if not last_tick:
        return None
    try:
        then = datetime.fromisoformat(last_tick)
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).timestamp() - then.timestamp()


def should_nudge(last_nudged: float | None, now: datetime | None = None, rewake_s: int = REWAKE_S) -> bool:
    """Is it time to nudge again, given when (unix seconds, or None if never) it was last nudged?

    nemik:W18/luthen W117: the backoff+dedup decision luthen's checks/waker.py currently
    reinvents per-repo (a REWAKE_S threshold plus a seen-timestamp file). This is that decision,
    factored out as a pure function -- it takes no side effect and owns no state file itself;
    the caller decides WHICH rows are nudge candidates (e.g. state in asleep/idle, or
    stale/future/unknown) and where `last_nudged` came from and gets recorded.
    """
    if last_nudged is None:
        return True
    return (now or datetime.now(timezone.utc)).timestamp() - last_nudged >= rewake_s


def roster(g: Graph, liveness: dict, *, now: datetime | None = None) -> list[dict]:
    """One row per workstream something is waiting on, sleepers with waiters first."""
    rows: dict[str, dict] = {}
    for b in inbound(g):
        rec = liveness.get(b["blocker"])
        last_tick = (rec or {}).get("last_tick") or ""
        row = rows.setdefault(b["blocker"], {
            "repo": b["blocker"],
            "state": "unknown" if rec is None else AWAKE.get(rec.get("verdict"), "idle"),
            "last_tick": last_tick,
            "last_tick_age_s": age_seconds(last_tick, now),
            "waiting": [],
        })
        row["waiting"].append({"blocked": b["blocked"], "claimed_by": b["claimed_by"], "title": b["title"]})
    order = {"asleep": 0, "idle": 1, "unknown": 2, "awake": 3}
    return sorted(rows.values(), key=lambda r: (order[r["state"]], -len(r["waiting"]), r["repo"]))


def operator_row(g: Graph) -> dict:
    needs = [a for a in operator_asks(g) if a["category"] == "needs-you"]
    return {"repo": "operator", "state": "you", "last_tick": "",
            "waiting": [{"blocked": a["ref"], "claimed_by": [], "title": a["ask"]} for a in needs]}


def nudges_path() -> Path:
    import os

    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(state) / "nemik" / "nudges.json"


def due_nudges(rows: list[dict], seen: dict, now: datetime | None = None) -> list[dict]:
    """Rows worth nudging now (asleep or idle, something waiting, backoff not active).

    `seen` is {repo: unix_seconds_last_nudged}, read and written by the caller (nudges_path() by
    default) -- should_nudge() itself owns no state file. Mutates `seen` in place for the repos
    returned, so a caller can write it straight back out.
    """
    now = now or datetime.now(timezone.utc)
    due = []
    for r in rows:
        if r["state"] not in ("asleep", "idle") or not r["waiting"]:
            continue
        if not should_nudge(seen.get(r["repo"]), now):
            continue
        seen[r["repo"]] = now.timestamp()
        due.append(r)
    return due


def main() -> None:
    import argparse

    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(prog="nemik-wake", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument("--liveness", help="loop_liveness JSON file, or - for stdin")
    ap.add_argument("--all", action="store_true", help="include awake workstreams")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--nudge", action="store_true",
                     help="print only rows due a nudge now (backoff/dedup via --nudges-state)")
    ap.add_argument("--nudges-state", type=Path, default=nudges_path())
    args = ap.parse_args()
    g = Graph()
    for _, qg, _ in survey(args.root):
        if qg is not None:
            g += qg
    live, source = read_liveness(args.root, args.liveness)
    rows = [r for r in roster(g, live) if args.all or r["state"] != "awake"]
    if args.nudge:
        try:
            seen = json.loads(args.nudges_state.read_text())
        except (OSError, ValueError):
            seen = {}
        rows = due_nudges(rows, seen)
        args.nudges_state.parent.mkdir(parents=True, exist_ok=True)
        args.nudges_state.write_text(json.dumps(seen))
    if args.json:
        print(json.dumps({"liveness": source, "roster": rows, "operator": operator_row(g)}, indent=2))
        return
    print(f"liveness: {source}")
    for r in rows:
        print(f"\n{r['state'].upper():7} {r['repo']}  ({len(r['waiting'])} waiting; last tick {r['last_tick'] or 'none'})")
        for w in r["waiting"]:
            claim = ", ".join(w["claimed_by"]) or f"waiting on {r['repo']}: claim with --enables {w['blocked']}"
            print(f"          {w['blocked']:28} {claim:22} {w['title'][:60]}")
    op = operator_row(g)
    print(f"\nYOU     operator  ({len(op['waiting'])} need you: nemik-operator)")
