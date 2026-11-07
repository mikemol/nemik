# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: run the repo's nemik hooks against a source tree, the "hooks still import" check.

A new `src/nemik` module breaks the live readers (relay, hooks, commands) until the venv is built,
and a hub the hooks import (serve, check) can break them on its own. The two hooks in
.claude/settings.json that import nemik are run here with PYTHONPATH on the given source directory
and a one-line PreToolUse (or PostToolUse) payload on stdin, as Claude Code would send it. Each
prints `OK` when the hook exits 0 and prints no traceback, and `FAIL` with its first stderr line
otherwise.

    hookcheck.py VENV_BIN SRC

VENV_BIN is the directory holding the mikemol-hook-* commands, SRC the nemik source directory.
"""

import json
import os
import sys
from pathlib import Path

from mikemol.procrun.proc import capture

HOOKS = (
    ("mikemol-hook-inbound-asks", "PreToolUse"),
    ("mikemol-hook-inbound-asks", "PostToolUse"),
    ("mikemol-hook-nemik-check", "PreToolUse"),
    ("mikemol-hook-nemik-check", "PostToolUse"),
)
USAGE_ERROR = 2
ARGS = 2


def payload(event: str) -> str:
    """Write the one-line payload Claude Code sends a hook for a harmless Bash call.

    Returns:
        The JSON text.

    """
    body = {
        "hook_event_name": event,
        "tool_name": "Bash",
        "tool_input": {"command": "true"},
        "session_id": "hookcheck",
    }
    return json.dumps(body)


def verdict(hook: str, event: str, status: int, stderr: str) -> str:
    """Judge one hook run: the hook exits 0 and prints no traceback.

    Returns:
        An OK line, or a FAIL line carrying the first line of stderr.

    """
    bad = status != 0 or "Traceback" in stderr
    first = stderr.strip().splitlines()[0] if stderr.strip() else ""
    if bad:
        return f"FAIL  {hook} {event} rc={status}: {first[:120]}"
    return f"OK    {hook} {event} rc={status}"


def run_all(venv_bin: Path, src: Path) -> list[str]:
    """Run every hook with the source directory first on the import path.

    Returns:
        One verdict line per hook and event.

    """
    env = dict(os.environ, PYTHONPATH=str(src))
    lines = []
    for hook, event in HOOKS:
        done = capture(
            [str(venv_bin / hook)],
            env=env,
            input_text=payload(event),
        )
        lines.append(verdict(hook, event, done.returncode, done.stderr))
    return lines


def main(argv: list[str]) -> int:
    """Print the verdict lines for the hooks against a source tree.

    Returns:
        0 when every hook is OK, 1 when any fails, 2 on a usage error.

    """
    if len(argv) != ARGS:
        sys.stderr.write(__doc__ or "")
        return USAGE_ERROR
    lines = run_all(Path(argv[0]), Path(argv[1]))
    sys.stdout.write("\n".join(lines) + "\n")
    return int(any(line.startswith("FAIL") for line in lines))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
