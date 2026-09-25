"""nemik-check: validate every workstream's queue against nemik's SHACL shapes.

Exit 0 when every queue under the root translates with no sh:Violation; exit 1 otherwise.
sh:Warning results (vocabulary divergence not yet agreed across repos, stale edges into residue)
are printed but do not fail the check: divergence is reported to summit's floor, not enforced. This is the check summit registers the capability against.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path

from mikemol.pathsforward.store import UnreadableStateError
from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import SH

from nemik.adapter import bind, queue_graph

QUEUE, LEDGER = "paths-forward.json", "paths-forward.ledger"


def default_root() -> Path:
    """$NEMIK_ROOT, else ~/github."""
    return Path(os.environ.get("NEMIK_ROOT") or Path.home() / "github")


def workstream_files(root: Path, name: str) -> list[tuple[str, Path]]:
    """(repo, path) for `name` under either layout, keyed by repo.

    ~/github layout: <root>/<repo>/.claude/<name>. Export layout (luthen's host-side copy, which
    carries only these two files per repo): <root>/<repo>/<name>.
    """
    found = {p.parents[1].name: p for p in root.glob(f"*/.claude/{name}")}
    found |= {p.parent.name: p for p in root.glob(f"*/{name}")}
    return sorted(found.items())


def shapes() -> Graph:
    g = Graph()
    g.parse(data=files("nemik.data").joinpath("shapes.ttl").read_text(), format="turtle")
    return g


Finding = tuple[str, str, str]  # (severity, focus symbol, message)


def survey(root: Path) -> Iterator[tuple[str, Graph | None, list[Finding]]]:
    """Yield (repo, graph, findings) per queue; graph is None when mtools refuses the file."""
    shacl = shapes()
    queues = workstream_files(root, QUEUE)
    known = frozenset(repo for repo, _ in queues)
    for repo, state_path in queues:
        try:
            g = queue_graph(repo, state_path, known)
        except UnreadableStateError as exc:
            yield repo, None, [("Unreadable", "--", str(exc))]
            continue
        _, results, _ = validate(g, shacl_graph=shacl)
        findings = sorted(
            (str(sev).rsplit("#", 1)[-1], str(focus).rsplit("/", 1)[-1], str(msg))
            for focus, sev, msg in results.query(
                "SELECT ?f ?s ?m WHERE { ?r sh:focusNode ?f ; sh:resultSeverity ?s ; sh:resultMessage ?m }",
                initNs={"sh": SH},
            )
        )
        yield repo, g, findings


def main() -> None:
    ap = argparse.ArgumentParser(prog="nemik-check", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument("--dump", type=Path, help="write the merged graph as Turtle")
    args = ap.parse_args()

    merged, failed = bind(Graph()), 0
    for repo, g, findings in survey(args.root):
        if g is None:
            print(f"UNREADABLE {repo}: {findings[0][2]}")
            failed += 1
            continue
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
