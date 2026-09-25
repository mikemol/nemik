"""nemik-check: validate every workstream's queue against nemik's SHACL shapes.

Exit 0 when every queue under the root translates with no sh:Violation; exit 1 otherwise.
sh:Warning results (vocabulary divergence not yet agreed across repos, stale edges into residue)
are printed but do not fail the check: divergence is reported to summit's floor, not enforced. This is the check summit registers the capability against.
"""

from __future__ import annotations

import argparse
import sys
from importlib.resources import files
from pathlib import Path

from mikemol.pathsforward.store import UnreadableStateError
from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import SH

from nemik.adapter import bind, queue_graph

STATE_FILE = Path(".claude/paths-forward.json")


def shapes() -> Graph:
    g = Graph()
    g.parse(data=files("nemik.data").joinpath("shapes.ttl").read_text(), format="turtle")
    return g


def main() -> None:
    ap = argparse.ArgumentParser(prog="nemik-check", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path.home() / "github")
    ap.add_argument("--dump", type=Path, help="write the merged graph as Turtle")
    args = ap.parse_args()

    merged, failed = bind(Graph()), 0
    for state_path in sorted(args.root.glob(f"*/{STATE_FILE}")):
        repo = state_path.parents[1].name
        try:
            g = queue_graph(repo, state_path)
        except UnreadableStateError as exc:
            print(f"UNREADABLE {repo}: {exc}")
            failed += 1
            continue
        _, results, _ = validate(g, shacl_graph=shapes())
        findings = sorted(
            (str(sev).rsplit("#", 1)[-1], str(focus).rsplit("/", 1)[-1], str(msg))
            for focus, sev, msg in results.query(
                "SELECT ?f ?s ?m WHERE { ?r sh:focusNode ?f ; sh:resultSeverity ?s ; sh:resultMessage ?m }",
                initNs={"sh": SH},
            )
        )
        violates = any(sev == "Violation" for sev, _, _ in findings)
        print(f"{'VIOLATES  ' if violates else 'OK        '}{repo}")
        for sev, focus, msg in findings:
            print(f"  {sev:9} {focus:6} {msg}")
        failed += violates
        merged += g
    if args.dump:
        merged.serialize(destination=args.dump, format="turtle")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
