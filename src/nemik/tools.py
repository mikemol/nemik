"""nemik:W81: the read-only CLIs' exact output, rendered from an already-built graph.

Each command here is the CLI's own `main`, handed the server's cached graph instead of re-reading
every queue, with stdout captured. The text is therefore what the terminal would print, not a
second rendering that could drift from it. Only fixed argument lists are run: a request picks a
command and a repo, never flags, so nothing reachable from the web can write (`nemik-wake --nudge`
writes its backoff state and is not offered).
"""

from __future__ import annotations

import contextlib
import io
import re
import threading
from collections.abc import Callable

from rdflib import Graph

from nemik import blocks, check, floorasks, metrics, overlaps, rank, wake, witnesses

# name -> (main, argv for a repo or None, whether a repo is required)
COMMANDS: dict[str, tuple[Callable[..., None], Callable[[str | None], list[str]], bool]] = {
    "rank": (rank.main, lambda r: [r or ""], True),
    "goals": (rank.main, lambda r: [r or "", "--goals"], True),
    "rank-check": (rank.main, lambda r: [r or "", "--check"], True),
    "overlaps": (overlaps.main, lambda r: [], False),
    "overlaps-cross": (overlaps.main, lambda r: ["--cross"], False),
    "inbound": (blocks.main, lambda r: [r] if r else [], False),
    "operator": (blocks.operator_main, lambda r: [], False),
    "wake": (wake.main, lambda r: ["--all"], False),
}

# nemik:W82: commands that read the queue files themselves (they need more than the graph).
# Same fixed-argv rule; `witnesses` is the dry run, never --apply, and its observers may reach the
# network, so the panel runs it only on an explicit pick.
FILE_COMMANDS: dict[str, tuple[Callable[..., None], Callable[[str | None], list[str]], bool]] = {
    "check": (check.main, lambda r: [], False),
    "metrics": (metrics.main, lambda r: [], False),
    "floor-asks": (floorasks.main, lambda r: [], False),
    "witnesses": (witnesses.main, lambda r: [], False),
}


def _pf(flag: str) -> Callable[..., None]:
    """nemik:W83: mtools' own read-only view of one repo's queue, through the pinned library (the same
    code as the mikemol-paths-forward CLI, no subprocess). argv arrives as [repo, "--root", root]."""

    def run_pf(argv: list[str]) -> None:
        from pathlib import Path

        from mikemol.pathsforward.cli import main as pf_main

        from nemik.check import QUEUE, workstream_files

        repo, root = argv[0], Path(argv[2])
        paths = [p for r, p in workstream_files(root, QUEUE) if r == repo]
        if not paths:
            print(f"no queue for {repo} under {root}")
            raise SystemExit(2)
        raise SystemExit(pf_main(["--state", str(paths[0]), flag]))

    return run_pf


FILE_COMMANDS.update({
    "pf-queue": (_pf("--queue"), lambda r: [r or ""], True),
    "pf-check": (_pf("--check"), lambda r: [r or ""], True),
    "pf-overlaps": (_pf("--overlaps"), lambda r: [r or ""], True),
})

# redirect_stdout swaps a process-wide object, so two requests at once would interleave.
_stdout = threading.Lock()


def run(name: str, g: Graph, root: str, repo: str | None = None) -> tuple[int, str]:
    """(exit code, stdout) of command `name` over `g`; ValueError for an unknown command or bad repo."""
    table = COMMANDS if name in COMMANDS else FILE_COMMANDS
    if name not in table:
        raise ValueError(f"unknown command {name!r}; one of {', '.join([*COMMANDS, *FILE_COMMANDS])}")
    fn, argv, needs_repo = table[name]
    if repo is not None and not re.fullmatch(r"[\w.-]+", repo):
        raise ValueError(f"bad repo {repo!r}")
    if needs_repo and not repo:
        raise ValueError(f"{name} needs ?repo=")
    buf = io.StringIO()
    code = 0
    with _stdout, contextlib.redirect_stdout(buf):
        try:
            args = [*argv(repo), "--root", root]
            fn(args, g=g) if table is COMMANDS else fn(args)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
    return code, buf.getvalue()
