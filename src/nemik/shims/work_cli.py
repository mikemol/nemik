# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""The CPython entry of nemik-work, and the callers' view of its tool lookups (nemik:W2125).

nemik.work compiles under the pinned Codon, which has no sys.executable and no tempfile, so it
takes an Env: the directory the mikemol tools are installed in and the root scratch directories
are made under. Here those are where they always were: beside the running interpreter (the
venv's bin), never a PATH lookup, which could find a tool that is not the pinned one, and the
system temp directory. `cli` is the nemik-work console script; `run_writer` and `in_gate` are the
two calls that nemik-ask, nemik-witnesses, nemik-check and the stalled report make, with the Env
filled in.
"""

import sys
import tempfile
from pathlib import Path

from nemik import work


def env() -> work.Env:
    """Build the Env of this process: its interpreter's directory and the system temp directory.

    Returns:
        The Env nemik.work takes.

    """
    return work.Env(str(Path(sys.executable).parent), tempfile.gettempdir())


def run_writer(argv: list[str]) -> tuple[int, str]:
    """Run the one writer, mikemol-paths-forward, from the interpreter's directory.

    Returns:
        The writer's exit status and its output (stderr when it failed, else stdout).

    """
    return work.run_writer(argv, env())


def in_gate(repo_dir: Path) -> set[str]:
    """Name the waypoints a queued or gating commit stack of this repo carries.

    Returns:
        The waypoint symbols of the live stacks.

    """
    return work.in_gate(repo_dir, env())


def cli() -> int:
    """Run nemik-work: main over the process's own arguments and this process's Env.

    Returns:
        What nemik.work.main returns for the command line.

    """
    return work.main(sys.argv[1:], env())


if __name__ == "__main__":
    raise SystemExit(cli())
