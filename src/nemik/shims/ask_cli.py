# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""The CPython entry of nemik-ask (nemik:W2164).

nemik.ask_cli compiles under the pinned Codon, which has no sys.executable, no tempfile and no
argparse, so it reads its own command line and takes an Env. Here the Env is what it always was:
the directory beside the running interpreter (the venv's bin) and the system temp directory, filled
in by nemik.shims.work_cli. `cli` is the nemik-ask console script.
"""

import sys

from nemik import ask_cli
from nemik.shims.work_cli import env


def cli() -> int:
    """Run nemik-ask: main over the process's own arguments and this process's Env.

    Returns:
        What nemik.ask_cli.main returns for the command line.

    """
    return ask_cli.main(sys.argv[1:], env())


if __name__ == "__main__":
    raise SystemExit(cli())
