# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1562: where a workstream's queue files live, below check and history.

nemik.check and nemik.history both need the queue and ledger file names, the default root and the
list of workstreams under a root. They lived in check, so history imported check while check's
stalled-card findings needed history: a cycle, held apart by a function-local import. They sit here
instead, a leaf that imports only the standard library, and check re-exports each name.
"""

import os
from pathlib import Path

QUEUE, LEDGER = "paths-forward.json", "paths-forward.ledger"


def default_root() -> Path:
    """$NEMIK_ROOT, else ~/github.

    Returns:
        The directory named by $NEMIK_ROOT, else ~/github.

    """
    return Path(os.environ.get("NEMIK_ROOT") or Path.home() / "github")


def workstream_files(root: Path, name: str) -> list[tuple[str, Path]]:
    """(repo, path) for `name` under either layout, keyed by repo.

    ~/github layout: <root>/<repo>/.claude/<name>. Export layout (luthen's host-side copy, which
    carries only these two files per repo): <root>/<repo>/<name>.

    Returns:
        The (repo, path) pairs sorted by repo, leaving out dot-named directories.

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
