# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W635: write each repo's version-2 export from the queues and luthen's version-1 list.

The compatible-first step of docs/withholding-at-source.md as a command: until a repo's own writer
emits its export, the pod's builder derives them here and hands the directory to
`nemik-serve --publish --exports`. A repo whose own export exists elsewhere simply replaces the
derived file.
nemik:W873: that replacing is done here: a repo's own export, `paths-forward.export.json` beside its
queue (mtools:W1838), is written out as it stands when it is valid for the repo and no older than
its queue; otherwise the export is derived from luthen's list as before.
"""

import argparse
import sys
from pathlib import Path

from nemik.check import QUEUE, default_root, workstream_files
from nemik.exportcompat import derive, write
from nemik.exportv2 import own_export
from nemik.exportwire import repo_symbols
from nemik.withheld import load


class _Options(argparse.Namespace):
    """The parsed command line, typed."""

    root: Path
    withheld: Path
    out: Path


def main(argv: list[str] | None = None) -> None:
    """Write <repo>.json under --out for every repo under --root.

    Args:
        argv: The command line after the program name, or None for sys.argv.

    """
    ap = argparse.ArgumentParser(
        prog="nemik-exports", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument(
        "--withheld", type=Path, required=True, help="luthen's withheld list (v1)"
    )
    ap.add_argument("--out", type=Path, required=True, help="the exports directory")
    args = ap.parse_args(argv, namespace=_Options())
    refs = set(load(args.withheld))
    args.out.mkdir(parents=True, exist_ok=True)
    found = repo_symbols(args.root)
    states = dict(workstream_files(args.root, QUEUE))
    own = 0
    for repo, symbols in found.items():
        mine: dict[str, object] = {}
        if repo in states:
            state = states[repo]
            mine = own_export(repo, state.with_name("paths-forward.export.json"), state)
        own += bool(mine)
        write(args.out / f"{repo}.json", mine or derive(repo, symbols, refs))
    sys.stdout.write(f"{len(found)} export(s) written to {args.out}\n")
    sys.stdout.write(f"{own} of them from the repo's own export\n")


if __name__ == "__main__":
    main()
