"""Fleet-wide touches[] overlap (nemik:W53), in the line shape of mtools' `--overlaps` (mtools:W118).

`OVERLAP <tag>: <repo>:W<a>,<repo>:W<b>` for each tag that two or more live (ready or working)
waypoints share. `--cross` keeps only tags shared across repos: the part a single queue's own
`--overlaps` cannot see. Advisory, like ATOMIZE: always exits 0.
"""

from rdflib import Graph
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, STATE
from nemik.blocks import _repo, ref

LIVE = {STATE["ready"], STATE["working"]}


def overlaps(g: Graph, cross: bool = False) -> dict[str, list[str]]:
    by_tag: dict[str, set[Node]] = {}
    for node, tag in g.subject_objects(NEMIK.touches):
        if g.value(node, OSLC_CM.state) in LIVE:
            by_tag.setdefault(str(tag), set()).add(node)
    out: dict[str, list[str]] = {}
    for name, nodes in sorted(by_tag.items()):
        if len(nodes) < 2 or (cross and len({_repo(n) for n in nodes}) < 2):
            continue
        out[name] = sorted(ref(n) for n in nodes)
    return out


def main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    import argparse
    from pathlib import Path

    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument(
        "--cross", action="store_true", help="only tags shared across repos"
    )
    args = ap.parse_args(argv)
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    for tag, refs in overlaps(g, args.cross).items():
        print(f"OVERLAP {tag}: {','.join(refs)}")
