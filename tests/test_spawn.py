# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2125: nemik.spawn.capture runs a program on os.system and keeps subprocess.run's contract.

The pinned Codon has no subprocess, so work.py starts its tools through nemik.spawn. These tests
run it under CPython against what subprocess would answer and pin the edges that matter: an
argument holding `$(...)`, backticks and a newline arrives unchanged, a timeout is status 124, a
missing program is status 127 with the shell's own text, output larger than a pipe buffer is not
lost, two spawns of one process never share a directory, a name that already exists is an error
and is never written through, and a root that cannot be written is an OSError, not an empty
Completed. The compiled module is checked by the Codon census and by running it natively (the
proof is recorded on nemik:W2125).
"""

import os
import time
from pathlib import Path

import pytest

from nemik import spawn

BIG = 3_000_000
TIMED_OUT = 124
NOT_FOUND = 127
PROMPT = 20.0
TICK = 0.1
WAIT_TICKS = 50
NONZERO = 3
TRICKY = "$(echo INJECT) `echo BT` ; echo X\nline2 | cat > /dev/null 'q' \"d\" é"


def test_a_program_that_succeeds_gives_its_output(tmp_path: Path) -> None:
    """Give status 0 with stdout and stderr kept apart."""
    done = spawn.capture(
        ["sh", "-c", "echo out; echo err 1>&2"], spawn.NO_LIMIT, str(tmp_path)
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "out\n", "err\n")


def test_a_nonzero_status_is_kept(tmp_path: Path) -> None:
    """Give the program's own exit status, not a wait status."""
    done = spawn.capture(["sh", "-c", "exit 3"], spawn.NO_LIMIT, str(tmp_path))
    assert done.returncode == NONZERO


def test_an_argument_with_shell_syntax_and_a_newline_arrives_unchanged(
    tmp_path: Path,
) -> None:
    """Pass command substitution, backticks, a newline, a pipe, quotes and non-ASCII literally."""
    done = spawn.capture(["printf", "%s", TRICKY], spawn.NO_LIMIT, str(tmp_path))
    assert done.stdout == TRICKY
    assert done.returncode == 0


def test_a_program_that_outlasts_the_timeout_is_124(tmp_path: Path) -> None:
    """Stop it with the coreutils timeout and say 124, as the writer and committer limits did."""
    done = spawn.capture(["sleep", "5"], 1, str(tmp_path))
    assert done.returncode == TIMED_OUT


def _alive(pid: int) -> bool:
    """Say whether a process is running (a zombie is not).

    Returns:
        True while `pid` exists and is not a zombie.

    """
    stat = Path(f"/proc/{pid}/stat")
    if not stat.exists():
        return False
    return not stat.read_text(encoding="utf-8").rpartition(")")[2].strip().startswith("Z")


def test_a_program_that_ignores_term_is_still_stopped(tmp_path: Path) -> None:
    """Kill on timeout, as subprocess.run does: a TERM-proof program does not hold the call."""
    started = time.monotonic()
    done = spawn.capture(["sh", "-c", "trap '' TERM; sleep 30"], 1, str(tmp_path))
    assert done.returncode == TIMED_OUT
    assert time.monotonic() - started < PROMPT


def test_a_forking_program_takes_its_grandchild_with_it(tmp_path: Path) -> None:
    """Signal the process group on timeout, so a grandchild does not outlive the call."""
    marker = tmp_path / "pid"
    script = f"sleep 30 & echo $! > {marker}; wait"
    done = spawn.capture(["sh", "-c", script], 1, str(tmp_path))
    assert done.returncode == TIMED_OUT
    pid = int(marker.read_text(encoding="utf-8").strip())
    for _ in range(WAIT_TICKS):
        if not _alive(pid):
            break
        time.sleep(TICK)
    assert not _alive(pid)


def test_a_program_name_starting_with_a_dash_is_a_command_not_an_option(
    tmp_path: Path,
) -> None:
    """Run `-nemik-x` as a command (127), with a limit, not as an option of timeout."""
    done = spawn.capture(["-nemik-x"], 1, str(tmp_path))
    assert done.returncode == NOT_FOUND
    assert "-nemik-x" in done.stderr


def test_output_that_is_not_utf8_raises_and_leaves_nothing_behind(
    tmp_path: Path,
) -> None:
    """Read strictly, as mikemol.procrun.capture does, and still remove the directory."""
    with pytest.raises(UnicodeDecodeError):
        spawn.capture(["printf", "\\377"], spawn.NO_LIMIT, str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_a_missing_program_is_127_with_the_shells_own_text(tmp_path: Path) -> None:
    """Say command not found where subprocess raises FileNotFoundError: work looks first."""
    done = spawn.capture(["nemik-no-such-program-xyz"], spawn.NO_LIMIT, str(tmp_path))
    assert done.returncode == NOT_FOUND
    assert "not found" in done.stderr


def test_output_larger_than_a_pipe_buffer_is_not_lost(tmp_path: Path) -> None:
    """Return three megabytes whole, since the streams go to files."""
    done = spawn.capture(
        ["sh", "-c", f"head -c {BIG} /dev/zero | tr '\\0' x"],
        spawn.NO_LIMIT,
        str(tmp_path),
    )
    assert done.returncode == 0
    assert len(done.stdout) == BIG


def test_two_spawns_never_share_a_directory_and_leave_none_behind(
    tmp_path: Path,
) -> None:
    """Keep the names apart with the counter, and remove every private directory."""
    first = spawn.private_name(str(tmp_path))
    second = spawn.private_name(str(tmp_path))
    assert first != second
    spawn.capture(["echo", "a"], spawn.NO_LIMIT, str(tmp_path))
    spawn.capture(["echo", "b"], spawn.NO_LIMIT, str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_a_name_that_exists_is_an_error_and_is_not_written_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise on a collision, since mkdir fails on an existing name, and leave what was there."""
    monkeypatch.setattr(time, "time", lambda: 1.0)
    monkeypatch.setattr(spawn, "COUNTER", [0])
    taken = tmp_path / f"nemik-spawn-{os.getpid()}-1000000-1"
    taken.mkdir()
    (taken / "marker").write_text("mine", encoding="utf-8")
    with pytest.raises(OSError, match="exists"):
        spawn.capture(["echo", "x"], spawn.NO_LIMIT, str(tmp_path))
    assert (taken / "marker").read_text(encoding="utf-8") == "mine"


def test_a_root_that_cannot_be_written_is_an_error(tmp_path: Path) -> None:
    """Raise OSError for a root that is missing and for one that is read-only."""
    with pytest.raises(OSError, match="No such file"):
        spawn.capture(["echo", "x"], spawn.NO_LIMIT, str(tmp_path / "nope"))
    if os.geteuid() == 0:
        pytest.skip("root can write a read-only directory")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        with pytest.raises(OSError, match="Permission denied"):
            spawn.capture(["echo", "x"], spawn.NO_LIMIT, str(locked))
    finally:
        locked.chmod(0o700)
