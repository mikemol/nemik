"""nemik-metrics: print nemik's state as Prometheus text exposition (for vmagent's import).

    nemik_waypoints{repo,state}              waypoints per OSLC state (ready|working|blocked|done|dropped)
    nemik_waypoints_minted{repo,during}      waypoints by mtools' minted_during (tick|interrupt);
                                             absent on waypoints minted before mtools 2e21902
    nemik_findings{repo,severity}            SHACL results per severity (Violation|Warning|Unreadable)
    nemik_prompts_total{repo,source,class}   prompts recorded by the global hook, where class is
                                             forecast (scheduled or operator-typed tick),
                                             interrupt (operator, peer), internal (subagent
                                             hand-backs, background notices: the session's own
                                             work returning), or unknown (a source string not in
                                             this module's own CLASS map -- a new hook source,
                                             not yet classified here)
    nemik_turns_total{repo}                  turns ended (Stop events)
    nemik_ledger_lines{repo,class,kind}      parsed ledger lines (mtools ledger.read) by effort class
    nemik_blocks_inbound{repo,claimed}       open waypoints in OTHER workstreams waiting on repo;
                                             claimed="false" when no waypoint of repo names them
    nemik_waiting_on{repo,state}             open waypoints elsewhere waiting on repo, by repo's
                                             liveness (asleep|idle|awake|unknown)
    nemik_pathsforward_adoption{repo,state}  1 per repo: declared|owner|missing|no-pyproject|unobservable
    nemik_ledger_unparsed{repo}              legacy/malformed ledger lines mtools returned unparsed
    nemik_realizability_waypoints{repo,coordinate}
                                             live waypoints per realizability coordinate
                                             (none|constructible|reachable|observable|coverable),
                                             judged by mtools' policy under the pinned opa
    nemik_realizability_unjudged{repo}       1 for a repo whose queue could not be judged (no pinned
                                             opa, an unreadable queue): absent coordinates are
                                             "not checked", never "clean"

    nemik_waypoint_age_seconds{repo,state,quantile}
                                             age of the open waypoints per state, from issued_at:
                                             quantile 0.5 is the median, 1 the oldest (W270)

Pushing is not nemik's job: luthen hosts the push path, which admits metric names only when
its policy entails them. This command prints, and the host decides what to import.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from mikemol.pathsforward.lock import stamp
from mikemol.pathsforward.opa_eval import OpaUnavailableError
from mikemol.pathsforward.store import UnreadableStateError
from rdflib import RDF, Graph
from rdflib.namespace import PROV

from nemik.adapter import BASE, NEMIK, OSLC_CM, ledger_graph
from nemik.blocks import inbound
from nemik.check import LEDGER, QUEUE, default_root, survey, workstream_files
from nemik.realize import verdicts
from nemik.wake import read_liveness, roster

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


def realizability_lines(root: Path) -> list[str]:
    """One gauge row per repo and coordinate; a queue that cannot be judged is flagged, not zeroed."""
    out = ["# TYPE nemik_realizability_waypoints gauge"]
    out.append("# TYPE nemik_realizability_unjudged gauge")
    now = stamp(datetime.now(UTC))
    for repo, path in workstream_files(root, QUEUE):
        try:
            found = verdicts(repo, path, root, now)
        except (OpaUnavailableError, UnreadableStateError):
            out.append(f"nemik_realizability_unjudged{label(repo=repo)} 1")
            continue
        by_level = Counter(str(v.get("level")) for v in found)
        for level, n in sorted(by_level.items()):
            out.append(
                f"nemik_realizability_waypoints{label(repo=repo, coordinate=level)} {n}"
            )
    return out


def age_lines(repo: str, g: Graph, now: datetime) -> list[str]:
    """nemik:W270: how long the open waypoints of `repo` have existed, per OSLC state, as a
    summary-style gauge: quantile 0.5 is the median age and quantile 1 the oldest. Per-waypoint
    series would be thousands of labels, and the question ("how long has the oldest one sat") is
    the quantile. Age runs from `issued_at`; a waypoint with none is left out, not counted as new."""
    from rdflib.namespace import DCTERMS

    ages: dict[str, list[float]] = {}
    for node, _, created in g.triples((None, DCTERMS.created, None)):
        state = g.value(node, OSLC_CM.state)
        if state is None:
            continue
        try:
            born = datetime.fromisoformat(str(created))
        except ValueError:
            continue
        name = str(state).rsplit("#", 1)[-1].lower()
        if name in ("done", "dropped"):
            continue
        ages.setdefault(name, []).append(max(0.0, (now - born).total_seconds()))
    out: list[str] = []
    for name, seen in sorted(ages.items()):
        seen.sort()
        for quantile, value in (("0.5", seen[len(seen) // 2]), ("1", seen[-1])):
            out.append(
                f"nemik_waypoint_age_seconds{label(repo=repo, state=name, quantile=quantile)}"
                f" {value:.0f}"
            )
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="nemik-metrics", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument("--spool", type=Path, default=spool_path())
    args = ap.parse_args(argv)

    out = [
        "# TYPE nemik_waypoints gauge",
        "# TYPE nemik_waypoints_minted gauge",
        "# TYPE nemik_findings gauge",
        "# TYPE nemik_waypoint_age_seconds gauge",
    ]
    now = datetime.now(UTC)
    for repo, g, findings in survey(args.root):
        states: Counter[str] = Counter()
        if g is not None:
            out += age_lines(repo, g, now)
        if g is not None:
            for _, _, st in g.triples((None, OSLC_CM.state, None)):
                states[str(st).rsplit("#", 1)[-1].lower()] += 1
            states["dropped"] = sum(1 for _ in g.subjects(RDF.type, NEMIK.Dropped))
        for name, n in sorted(states.items()):
            out.append(f"nemik_waypoints{label(repo=repo, state=name)} {n}")
        if g is not None:
            for during, n in sorted(
                Counter(str(o) for o in g.objects(None, NEMIK.mintedDuring)).items()
            ):
                out.append(
                    f"nemik_waypoints_minted{label(repo=repo, during=during)} {n}"
                )
        for sev, n in sorted(Counter(sev for sev, _, _ in findings).items()):
            out.append(f"nemik_findings{label(repo=repo, severity=sev)} {n}")

    merged = Graph()
    for _, g, _ in survey(args.root):
        if g is not None:
            merged += g
    out.append("# TYPE nemik_blocks_inbound gauge")
    inb = Counter(
        (b["blocker"], str(bool(b["claimed_by"])).lower()) for b in inbound(merged)
    )
    for (repo, claimed), n in sorted(inb.items()):
        out.append(f"nemik_blocks_inbound{label(repo=repo, claimed=claimed)} {n}")

    out.append("# TYPE nemik_pathsforward_adoption gauge")
    for ws, _, state in sorted(
        merged.triples((None, NEMIK.pathsforwardAdoption, None))
    ):
        out.append(
            f"nemik_pathsforward_adoption{label(repo=str(ws).removeprefix(BASE), state=str(state))} 1"
        )
    out.append("# TYPE nemik_waiting_on gauge")
    live, _ = read_liveness(args.root, None)
    for r in roster(merged, live):
        out.append(
            f"nemik_waiting_on{label(repo=r['repo'], state=r['state'])} {len(r['waiting'])}"
        )
    out += realizability_lines(args.root)

    prompts: Counter[tuple[str, str, str]] = Counter()
    turns: Counter[str] = Counter()
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
        out.append(
            f"nemik_prompts_total{label(repo=repo, source=src, **{'class': cls})} {n}"
        )
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
            out.append(
                f"nemik_ledger_lines{label(repo=repo, kind=kind, **{'class': cls})} {n}"
            )
        out.append(f"nemik_ledger_unparsed{label(repo=repo)} {unparsed}")
    print("\n".join(out))


if __name__ == "__main__":
    main()
