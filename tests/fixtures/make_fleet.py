"""Regenerate tests/fixtures/fleet/ from the live queues under ~/github (nemik:W125).

The layout test needs a graph with the fleet's real SHAPE: its repos, symbols, statuses and every
edge (enables, blocked_on citations, operator asks). It must not carry other repos' CONTENT into
nemik's tree, so titles, evidence and next steps are replaced, and the prose of an operator ask is
cut to its `operator: decide|act` head. Run it when the fleet's shape has drifted far enough that
the layout budgets no longer mean much; commit the result, and re-derive the budgets from it.

    .venv/bin/python3 tests/fixtures/make_fleet.py [~/github]
"""

import json
import re
import shutil
import sys
from pathlib import Path

KEEP = {"symbol", "status", "enables", "blocked_on", "blocked_kind", "minted_during"}
REF = re.compile(r"^(?:[\w.-]+:)?W\d+$")


def scrub_block(text: str) -> str:
    t = text.strip()
    if REF.match(t):
        return t
    m = re.match(r"^(operator)\s*:\s*(decide|act)\b", t, re.I)
    if m:
        return f"operator: {m[2].lower()} (fixture)"
    head = re.split(r"[\s:,(/]", t, maxsplit=1)[0]  # a repo or session name, the part nemik resolves
    return head


def main(root: Path, out: Path) -> None:
    shutil.rmtree(out, ignore_errors=True)
    for q in sorted(root.glob("*/.claude/paths-forward.json")):
        repo = q.parent.parent.name
        d = json.loads(q.read_text())
        wps = []
        for w in d.get("waypoints", []):
            x = {k: v for k, v in w.items() if k in KEEP}
            x["title"] = f"{repo} {w.get('symbol')}"
            x["blocked_on"] = [scrub_block(b) for b in (w.get("blocked_on") or [])]
            if w.get("caused_by"):
                x["caused_by"] = scrub_block(w["caused_by"])
            wps.append(x)
        res = [{"symbol": r.get("symbol"), "title": f"{repo} {r.get('symbol')}", "reason": "fixture",
                "dropped_at": "2026-09-28T00:00:00Z", "recoverable": True} for r in d.get("residue", [])]
        (out / repo).mkdir(parents=True)
        (out / repo / "paths-forward.json").write_text(json.dumps(
            {"version": 1, "project_root": f"/fixture/{repo}", "counter": d.get("counter", 0),
             "waypoints": wps, "residue": res}, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "github").expanduser(),
         Path(__file__).parent / "fleet")
