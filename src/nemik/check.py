"""nemik-check: validate every workstream's queue against nemik's SHACL shapes.

Exit 0 when every queue under the root translates with no sh:Violation; exit 1 otherwise.
Every run first prints `provenance:` lines: nemik's own commit (with `+uncommitted` when its
tree is dirty), and per queue `committed`, `uncommitted` or `untracked-source`. The exit code
means only the verdict.
sh:Warning results (vocabulary divergence not yet agreed across repos, stale edges into residue)
are printed but do not fail the check: divergence is reported to summit's floor, not enforced. This is the check summit registers the capability against.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path

from mikemol.pathsforward.store import UnreadableStateError
from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import SH

from nemik.adapter import BASE, bind, queue_graph
from nemik.blocks import annotate

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
    found |= {p.parent.name: p for p in root.glob(f"*/{name}") if p.parent.name != ".claude"}
    if not found and (root / ".claude" / name).exists():  # --root pointed at one repo
        found = {root.name: root / ".claude" / name}
    # A dot-named directory (e.g. .linux-sources-gate-wt, a git worktree of linux-sources) carries
    # another workstream's queue at another commit, not a workstream of its own; it cannot be
    # cited either, since mtools' <repo>:W<n> requires the repo to start alphanumeric. Counting it
    # doubled every block it holds and left the copies unclaimable.
    return sorted((repo, p) for repo, p in found.items() if not repo.startswith("."))


def shapes() -> Graph:
    g = Graph()
    g.parse(data=files("nemik.data").joinpath("shapes.ttl").read_text(), format="turtle")
    return g


Finding = tuple[str, str, str]  # (severity, focus symbol, message)


def survey(root: Path) -> Iterator[tuple[str, Graph | None, list[Finding]]]:
    """Yield (repo, graph, findings) per queue; graph is None when mtools refuses the file.

    Validation runs ONCE over the merged graph, so an `enables` edge into another workstream
    (`repo:W<n>`, legal since mtools 9236d5e) resolves against that workstream's waypoints.
    Each finding is attributed to the workstream of its focus node.
    """
    queues = workstream_files(root, QUEUE)
    known = frozenset(repo for repo, _ in queues)
    graphs: dict[str, Graph | None] = {}
    refused: dict[str, str] = {}
    merged = Graph()
    for repo, state_path in queues:
        try:
            graphs[repo] = queue_graph(repo, state_path, known)
            merged += graphs[repo]
        except UnreadableStateError as exc:
            graphs[repo], refused[repo] = None, str(exc)
    annotate(merged)
    _, results, _ = validate(merged, shacl_graph=shapes())
    by_repo: dict[str, list[Finding]] = {repo: [] for repo in graphs}
    for focus, sev, msg in results.query(
        "SELECT ?f ?s ?m WHERE { ?r sh:focusNode ?f ; sh:resultSeverity ?s ; sh:resultMessage ?m }",
        initNs={"sh": SH},
    ):
        repo, _, sym = str(focus).removeprefix(BASE).partition("/")
        by_repo.setdefault(repo, []).append((str(sev).rsplit("#", 1)[-1], sym or "--", str(msg)))
    for repo, g in graphs.items():
        if g is None:
            yield repo, None, [("Unreadable", "--", refused[repo])]
        else:
            yield repo, g, sorted(by_repo[repo])


def _git(cwd: Path, *argv: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(cwd), *argv], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def provenance(root: Path) -> list[str]:
    """What this verdict rests on: nemik's own commit, and each queue's committed-or-not state.

    One line per fact, prefixed `provenance:`, so a reader can grep them. A queue outside any git
    tree (luthen's export) reads `untracked-source`: its commit state is not observable from here.
    """
    here = Path(__file__).resolve().parent
    sha = _git(here, "rev-parse", "--short=12", "HEAD")
    dirty = _git(here, "status", "--porcelain", "--", ".")
    lines = [f"provenance: nemik {sha or 'unknown'}{' +uncommitted' if dirty else ''}"]
    for repo, path in workstream_files(root, QUEUE):
        top = _git(path.parent, "rev-parse", "--show-toplevel")
        if top is None:
            state = "untracked-source"
        else:
            changed = _git(path.parent, "status", "--porcelain", "--", str(path), str(path.with_name(LEDGER)))
            state = "uncommitted" if changed else "committed"
        lines.append(f"provenance: queue {repo} {state}")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(prog="nemik-check", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument("--dump", type=Path, help="write the merged graph as Turtle")
    args = ap.parse_args()

    for line in provenance(args.root):
        print(line)
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
