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
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path

from mikemol.pathsforward.store import UnreadableStateError
from pyshacl import validate
from rdflib import Graph, Literal
from rdflib.namespace import SH

from nemik.adapter import BASE, NEMIK, bind, queue_graph, workstream_uri
from nemik.adoption import adoption
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
    found |= {
        p.parent.name: p for p in root.glob(f"*/{name}") if p.parent.name != ".claude"
    }
    own = root / ".claude" / name
    if own.exists():
        # nemik:W224: a root with a queue of its own is a workstream too, named by its directory,
        # beside the workstreams it contains (the host queue at ~/github/.claude over every repo,
        # cited `github:W<n>`); a root that holds no repos (--root pointed at one repo) is the
        # same rule with nothing beneath it. A child of the same name wins. Resolved: `--root .`
        # has the name '' (nemik:W142), which left the workstream unnamed and its own
        # <repo>:W<n> references unresolvable.
        found.setdefault(root.resolve().name, own)
    # A dot-named directory (e.g. .linux-sources-gate-wt, a git worktree of linux-sources) carries
    # another workstream's queue at another commit, not a workstream of its own; it cannot be
    # cited either, since mtools' <repo>:W<n> requires the repo to start alphanumeric. Counting it
    # doubled every block it holds and left the copies unclaimable.
    return sorted((repo, p) for repo, p in found.items() if not repo.startswith("."))


def shapes() -> Graph:
    g = Graph()
    g.parse(
        data=files("nemik.data").joinpath("shapes.ttl").read_text(), format="turtle"
    )
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
            qg = queue_graph(repo, state_path, known)
            qg.add(
                (
                    workstream_uri(repo),
                    NEMIK.pathsforwardAdoption,
                    Literal(adoption(state_path)),
                )
            )
            graphs[repo] = qg
            merged += qg
        except UnreadableStateError as exc:
            graphs[repo], refused[repo] = None, str(exc)
    annotate(merged)
    from nemik.hostapply import HOST_REF, load

    # nemik:W256: a cited host-apply row the export does not hold is an unresolved citation. Only the
    # file is read (no exporter subprocess), and no export at all leaves the citation as it was.
    try:
        export = load(root, run_exporter=False)
    except ValueError:
        export = None
    if export is not None:
        for node, cited in list(merged.subject_objects(NEMIK.blockedOn)):
            m = HOST_REF.fullmatch(str(cited).strip())
            if m and m[1] not in export.rows:
                merged.add((node, NEMIK.unresolvedBlocker, cited))
    from nemik.shaclcache import cached_sparql_parse

    # nemik:W254: pyshacl hands rdflib the same constraint text for every focus node; parse it once.
    with cached_sparql_parse():
        _, results, _ = validate(merged, shacl_graph=shapes())
    by_repo: dict[str, list[Finding]] = {repo: [] for repo in graphs}
    for focus, sev, msg in results.query(
        "SELECT ?f ?s ?m WHERE { ?r sh:focusNode ?f ; sh:resultSeverity ?s ; sh:resultMessage ?m }",
        initNs={"sh": SH},
    ):
        repo, _, sym = str(focus).removeprefix(BASE).partition("/")
        by_repo.setdefault(repo, []).append(
            (str(sev).rsplit("#", 1)[-1], sym or "--", str(msg))
        )
    # nemik:W279: a letter a waypoint cites as evidence must exist (moved to inbox/archive counts).
    # The export layout carries no inbox, so a root without any inbox directory is not asked.
    if any(root.glob("*/inbox")):
        for node, _, cited in merged.triples((None, NEMIK.letter, None)):
            repo, _, sym = str(node).removeprefix(BASE).partition("/")
            rel = str(cited)
            path = root / (rel if "/inbox/" in rel else f"{repo}/{rel}")
            archived = path.parent / "archive" / path.name
            if not (path.exists() or archived.exists()):
                missing = (
                    f"cites the letter {rel}, which is not under the root: fix the path"
                )
                by_repo.setdefault(repo, []).append(("Warning", sym, missing))
    for repo, g in graphs.items():
        if g is None:
            yield repo, None, [("Unreadable", "--", refused[repo])]
        else:
            yield repo, g, sorted(by_repo[repo])


def _git(cwd: Path, *argv: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), *argv], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def exported_commit(queue_dir: Path) -> tuple[str, str] | None:
    """Read `commit.json` beside an exported queue (nemik:W7): {"sha": str, "dirty": bool}.

    luthen's nemik_export.py writes this so the pod can report real provenance instead of a
    blanket `untracked-source` for every repo (the export tree has no .git of its own to read).
    Returns (state, sha) or None if the file is absent, unreadable, or malformed -- callers then
    fall back to the untracked-source reading.
    """
    try:
        data = json.loads((queue_dir / "commit.json").read_text())
        sha = str(data["sha"])
        return ("uncommitted" if data["dirty"] else "committed", sha)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def provenance(root: Path) -> list[str]:
    """What this verdict rests on: nemik's own commit, and each queue's committed-or-not state.

    One line per fact, prefixed `provenance:`, so a reader can grep them. A queue outside any git
    tree (luthen's export) reads `untracked-source`, unless the exporter also wrote `commit.json`
    beside it (nemik:W7), in which case the real state and sha are reported, suffixed `@<sha>`.
    """
    here = Path(__file__).resolve().parent
    sha = _git(here, "rev-parse", "--short=12", "HEAD")
    dirty = _git(here, "status", "--porcelain", "--", ".")
    lines = [f"provenance: nemik {sha or 'unknown'}{' +uncommitted' if dirty else ''}"]
    for repo, path in workstream_files(root, QUEUE):
        top = _git(path.parent, "rev-parse", "--show-toplevel")
        if top is None:
            exported = exported_commit(path.parent)
            state = f"{exported[0]}@{exported[1]}" if exported else "untracked-source"
        else:
            changed = _git(
                path.parent,
                "status",
                "--porcelain",
                "--",
                str(path),
                str(path.with_name(LEDGER)),
            )
            state = "uncommitted" if changed else "committed"
        lines.append(f"provenance: queue {repo} {state}")
    return lines


def _realizability(root: Path) -> int:
    """Print every live waypoint's realizability coordinate and residue (nemik:W247).

    Exit 0 when every waypoint is runtime-valid, 1 when any carries residue, 2 when a queue could
    not be judged (no pinned opa, an unreadable queue): not checked never reads as clean.
    """
    from datetime import UTC, datetime

    from mikemol.pathsforward.lock import stamp
    from mikemol.pathsforward.opa_eval import OpaUnavailableError

    from nemik.marks import MARKS, policy_version, provenance, read
    from nemik.realize import rows, runtime_valid, verdicts

    now, residue, unjudged = stamp(datetime.now(UTC)), 0, 0
    version = policy_version()
    # nemik:W236: the clock is the policy's input, so the verdicts below are a function of it; say which.
    print(f"as_of {now}  policy {version[:12]}")
    for repo, path in workstream_files(root, QUEUE):
        try:
            found = verdicts(repo, path, root, now)
        except (OpaUnavailableError, UnreadableStateError) as exc:
            print(f"NOT JUDGED {repo}: {exc}")
            unjudged += 1
            continue
        # nemik:W234: the writer's persisted marks are read, not re-derived; a stale one is named.
        marks, unreadable = read(path.parent / MARKS)
        print(f"{repo}: {len(found)} waypoint(s), {unreadable} unreadable mark line(s)")
        for verdict in found:
            residue += not runtime_valid(verdict)
            symbol = str(verdict.get("ref")).rsplit(":", 1)[-1]
            source = provenance(marks.get(symbol), now, version)
            for line in rows(verdict, source):
                print(f"  {line}")
    return 2 if unjudged else int(residue > 0)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="nemik-check", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument("--dump", type=Path, help="write the merged graph as Turtle")
    ap.add_argument(
        "--realizability",
        action="store_true",
        help="print each live waypoint's realizability coordinate and residue ledger "
        "(mtools' policy under the pinned opa); exit 2 when a queue could not be judged",
    )
    ap.add_argument(
        "--committed",
        nargs="*",
        metavar="REPO",
        help="print the queue provenance lines and exit 4 when any named repo (none named: every "
        "repo) is read from an uncommitted or untracked queue: a claim about a peer reaches only "
        "as far as its last commit (nemik:W272, gcalculus:W224). Validates nothing.",
    )
    ap.add_argument(
        "--letters",
        action="store_true",
        help="check every letter under <repo>/inbox is addressed to that repo (its first line "
        "`from → to:`); exit 5 when one is misdelivered. Reads the receiving side only; validates "
        "nothing else (nemik:W271, gcalculus:W224)",
    )
    ap.add_argument(
        "--fold",
        action="store_true",
        help="with --letters: also list, as --add commands, every letter no waypoint of its repo "
        "cites (a letter is a waypoint's evidence in file form; nemik:W277). Applies nothing.",
    )
    args = ap.parse_args(argv)
    if args.realizability:
        sys.exit(_realizability(args.root))
    if args.letters:
        from nemik.letters import report

        said, code = report(
            args.root,
            {repo for repo, _ in workstream_files(args.root, QUEUE)},
            args.fold,
        )
        print("\n".join(said))
        sys.exit(code)
    if args.committed is not None:
        lines = provenance(args.root)
        for line in lines:
            print(line)
        named = set(args.committed)
        stale = [
            line
            for line in lines
            if line.startswith("provenance: queue ")
            and line.split()[3].split("@")[0] != "committed"
            and (not named or line.split()[2] in named)
        ]
        sys.exit(4 if stale else 0)

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
