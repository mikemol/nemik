"""nemik-metrics: print nemik's state as Prometheus text exposition (for vmagent's import).

    nemik_waypoints{repo,state}              waypoints per OSLC state (ready|working|blocked|done|dropped)
    nemik_waypoints_minted{repo,during}      waypoints by mtools' minted_during (tick|interrupt);
                                             absent on waypoints minted before mtools 2e21902
    nemik_findings{repo,severity}            SHACL results per severity (Violation|Warning|Unreadable)
    nemik_prompts_total{repo,source,class}   prompts recorded by the global hook, where class is
                                             forecast (scheduled or operator-typed tick),
                                             interrupt (operator, peer), or internal (subagent
                                             hand-backs, background notices: the session's own work returning)
    nemik_turns_total{repo}                  turns ended (Stop events)
    nemik_ledger_lines{repo,class,kind}      parsed ledger lines (mtools ledger.read) by effort class
    nemik_blocks_inbound{repo,claimed}       open waypoints in OTHER workstreams waiting on repo;
                                             claimed="false" when no waypoint of repo names them
    nemik_ledger_unparsed{repo}              legacy/malformed ledger lines mtools returned unparsed

Pushing is not nemik's job: luthen hosts the push path, which admits metric names only when
its policy entails them. This command prints, and the host decides what to import.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from rdflib import RDF, Graph
from rdflib.namespace import PROV

from nemik.adapter import NEMIK, OSLC_CM, ledger_graph
from nemik.blocks import inbound
from nemik.check import LEDGER, default_root, survey, workstream_files

CLASS = {
    "tick": "forecast",
    "operator-tick": "forecast",
    "operator": "interrupt",
    "peer": "interrupt",
    "subagent": "internal",
    "background": "internal",
}


def spool_path() -> Path:
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(state) / "nemik" / "events.jsonl"


def label(**kv: str) -> str:
    return "{" + ",".join(f'{k}="{v}"' for k, v in kv.items()) + "}"


def main() -> None:
    ap = argparse.ArgumentParser(prog="nemik-metrics", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument("--spool", type=Path, default=spool_path())
    args = ap.parse_args()

    out = ["# TYPE nemik_waypoints gauge", "# TYPE nemik_waypoints_minted gauge", "# TYPE nemik_findings gauge"]
    for repo, g, findings in survey(args.root):
        states = Counter()
        if g is not None:
            for _, _, st in g.triples((None, OSLC_CM.state, None)):
                states[str(st).rsplit("#", 1)[-1].lower()] += 1
            states["dropped"] = sum(1 for _ in g.subjects(RDF.type, NEMIK.Dropped))
        for st, n in sorted(states.items()):
            out.append(f"nemik_waypoints{label(repo=repo, state=st)} {n}")
        if g is not None:
            for during, n in sorted(Counter(str(o) for o in g.objects(None, NEMIK.mintedDuring)).items()):
                out.append(f"nemik_waypoints_minted{label(repo=repo, during=during)} {n}")
        for sev, n in sorted(Counter(sev for sev, _, _ in findings).items()):
            out.append(f"nemik_findings{label(repo=repo, severity=sev)} {n}")

    merged = Graph()
    for _, g, _ in survey(args.root):
        if g is not None:
            merged += g
    out.append("# TYPE nemik_blocks_inbound gauge")
    inb = Counter((b["blocker"], str(bool(b["claimed_by"])).lower()) for b in inbound(merged))
    for (repo, claimed), n in sorted(inb.items()):
        out.append(f"nemik_blocks_inbound{label(repo=repo, claimed=claimed)} {n}")

    prompts, turns = Counter(), Counter()
    if args.spool.exists():
        for raw in args.spool.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(raw)
            except json.JSONDecodeError:
                continue
            repo = e.get("repo") or "none"
            if e.get("event") == "UserPromptSubmit":
                src = e.get("source") or "unknown"
                prompts[(repo, src, CLASS.get(src, "unknown"))] += 1
            elif e.get("event") == "Stop":
                turns[repo] += 1
    out.append("# TYPE nemik_prompts_total counter")
    for (repo, src, cls), n in sorted(prompts.items()):
        out.append(f"nemik_prompts_total{label(repo=repo, source=src, **{'class': cls})} {n}")
    out.append("# TYPE nemik_turns_total counter")
    for repo, n in sorted(turns.items()):
        out.append(f"nemik_turns_total{label(repo=repo)} {n}")
    out += ["# TYPE nemik_ledger_lines gauge", "# TYPE nemik_ledger_unparsed gauge"]
    for repo, path in workstream_files(args.root, LEDGER):
        g, unparsed = ledger_graph(repo, path)
        lines = Counter(
            (str(c), str(k))
            for a in g.subjects(RDF.type, PROV.Activity)
            for c in g.objects(a, NEMIK.effortClass)
            for k in g.objects(a, NEMIK.kind)
        )
        for (cls, kind), n in sorted(lines.items()):
            out.append(f"nemik_ledger_lines{label(repo=repo, kind=kind, **{'class': cls})} {n}")
        out.append(f"nemik_ledger_unparsed{label(repo=repo)} {unparsed}")
    print("\n".join(out))


if __name__ == "__main__":
    main()
