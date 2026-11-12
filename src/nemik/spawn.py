# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Run a program and read what it printed, on os.system, which the pinned Codon can compile.

nemik:W2125. Codon has no subprocess and no tempfile, only `os.system(cmd) -> int`, the raw C
status with no output capture. `capture` quotes every argument (nemik.shellquote, so `$(...)`,
backticks, `;`, `|`, `>` and a newline reach the program as written), makes a private directory
with `Path.mkdir(mode=0o700)` (which fails if the name exists, so a planted path cannot be written
through), runs

    timeout N 'prog' 'arg'... >OUT 2>ERR; echo $? >STATUS

inside it, reads the three files back and removes them. The exit status comes from the STATUS
file, so no wait status is decoded. One code path serves CPython and Codon, since Codon compiles a
dead `if TYPE_CHECKING:` branch and a runtime split would not be skipped.

Contract, against subprocess.run: stdout and stderr are the program's, as text. A timeout of
NO_LIMIT (-1) runs without `timeout`; otherwise the coreutils `timeout` stops the program after
that many seconds, as the writer and committer limits always did (this adds no wall-clock limit).
`timeout -s KILL -- N` kills, as subprocess.run's timeout does (a SIGTERM could be ignored and
the wait would never end), and signals its own process group, so a grandchild dies with the
child. The status is then TIMED_OUT, 124: timeout itself exits 137 on KILL and that is mapped
here, so a program that kills itself with SIGKILL inside a limit reads the same. Output is read
as utf-8, strictly, as mikemol.procrun.capture's text=True reads it: bytes that are not utf-8
raise UnicodeDecodeError, never a quietly altered stream. A program that does not
exist is status 127 with the shell's own "command not found" on stderr (subprocess raises
FileNotFoundError); nemik.work looks the file up first. Anything that stops `capture` from
running the program at all (a root that is missing or not writable, a name that exists) is an
OSError, never an empty Completed.

The one os.system call is the point of the module, and the one place the house lint's shell rule
(S605) is relieved, in ruff-house.toml's per-file-ignores with this reason (nemik:W2125; Codon has
no subprocess). The scratch root is never defaulted here: the caller passes it.
"""

import os
import time
from pathlib import Path

from nemik.shellquote import quote

NO_LIMIT = -1
TIMED_OUT = 124
KILLED = 137
FAILED = 71
MICROSECONDS = 1000000
PRIVATE = 0o700
COUNTER = [0]


class Completed:
    """What a finished program left: its arguments, exit status and the two streams as text."""

    args: list[str]
    returncode: int
    stdout: str
    stderr: str

    def __init__(
        self, args: list[str], returncode: int, stdout: str, stderr: str
    ) -> None:
        """Hold the four fields."""
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def private_name(root: str) -> str:
    """Name a private directory under `root` from the pid, the clock and a counter.

    The counter keeps two spawns of one process in one microsecond apart.

    Returns:
        The directory's path.

    """
    COUNTER[0] += 1
    stamp = str(int(time.time() * MICROSECONDS))
    return f"{root}/nemik-spawn-{os.getpid()}-{stamp}-{COUNTER[0]}"


def capture(argv: list[str], timeout: int, root: str) -> Completed:
    """Run `argv` to completion with its output captured as text.

    Args:
        argv: The program and its arguments, never interpreted by a shell.
        timeout: Seconds the program may take, or NO_LIMIT.
        root: The directory the private working directory is made in.

    Returns:
        The completed program.

    """
    here = Path(private_name(root))
    here.mkdir(mode=PRIVATE)
    out, err, status = here / "out", here / "err", here / "status"
    try:
        words = " ".join([quote(a) for a in argv])
        if timeout != NO_LIMIT:
            words = "timeout -s KILL -- " + str(timeout) + " " + words
        redirect = " >" + quote(str(out)) + " 2>" + quote(str(err))
        os.system(words + redirect + "; echo $? >" + quote(str(status)))
        code = int(status.read_text(encoding="utf-8").strip())
        if timeout != NO_LIMIT and code == KILLED:
            code = TIMED_OUT
        return Completed(
            argv, code, out.read_text(encoding="utf-8"), err.read_text(encoding="utf-8")
        )
    finally:
        for name in (out, err, status):
            if name.exists():
                name.unlink()
        here.rmdir()
