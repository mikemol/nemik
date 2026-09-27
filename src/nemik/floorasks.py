"""Witness that summit floor asks point at live waypoints (nemik:W42).

Each `summit/floor/*.bib` entry may carry `waypoint = {<repo>:W<n>}`. The pointer must resolve to
a waypoint in that repo's queue that is not dropped; otherwise the ask cites nothing an agent owns.
"""

import argparse
import json
import re
from pathlib import Path

from nemik.check import QUEUE, default_root, workstream_files

# Same field regex as summit's scripts/place_intake.py (`waypoint` is a real top-level field).
_WAYPOINT = re.compile(r"^\s*waypoint\s*=\s*\{([^}]*)\}", re.MULTILINE)
_KEY = re.compile(r"^@\w+\{([^,\s]+),", re.MULTILINE)
_ENTRY = re.compile(r"^@\w+\{.*?^\}", re.MULTILINE | re.DOTALL)


def floor_asks(floor: Path) -> list[tuple[str, str]]:
    """(bib key, waypoint pointer) for every floor entry carrying a waypoint field."""
    out = []
    for bib in sorted(floor.glob("*.bib")):
        for block in _ENTRY.findall(bib.read_text(encoding="utf-8", errors="replace")):
            wp, key = _WAYPOINT.search(block), _KEY.search(block)
            if wp:
                out.append((key.group(1) if key else "?", wp.group(1).strip()))
    return out


def _statuses(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    st = {w["symbol"]: w.get("status", "") for w in data.get("waypoints", [])}
    st.update({r["symbol"]: "dropped" for r in data.get("residue", [])})
    return st


def unresolved(root: Path, floor: Path) -> list[tuple[str, str, str]]:
    """(key, pointer, why) for each ask whose waypoint is malformed, unknown, or dropped."""
    queues = dict(workstream_files(root, QUEUE))
    cache: dict[str, dict[str, str]] = {}
    bad = []
    for key, ptr in floor_asks(floor):
        repo, _, sym = ptr.partition(":")
        if not re.fullmatch(r"W\d+", sym):
            bad.append((key, ptr, "malformed")); continue
        if repo not in queues:
            bad.append((key, ptr, "no queue for repo")); continue
        st = cache.setdefault(repo, _statuses(queues[repo])).get(sym)
        if st is None:
            bad.append((key, ptr, "no such waypoint"))
        elif st == "dropped":
            bad.append((key, ptr, "dropped"))
    return bad


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github, or the export layout root")
    ap.add_argument("--floor", type=Path, help="default: <root>/summit/floor")
    args = ap.parse_args(argv)
    floor = args.floor or args.root / "summit" / "floor"
    n = len(floor_asks(floor))
    bad = unresolved(args.root, floor)
    for key, ptr, why in bad:
        print(f"floor-asks: {key}: {ptr}: {why}")
    print(f"floor-asks: {n - len(bad)} of {n} waypoint pointers resolve")
    raise SystemExit(1 if bad else 0)
