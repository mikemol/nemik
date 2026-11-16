# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""cpuline: the line a test run prints so the gate can read its CPU (nemik:W928, W923).

mtools' mutants runner and rules_py/pytest_main print `shard cpu=S children=K idle_wall=W`, and the
gate's per-target series reads it (mtools:W1873, W1798): wall seconds move with host load, CPU does
not, so a test's cost, and what to split it into, is measured from CPU. tests/conftest.py prints it
when a pytest session ends.

nemik:W1140: and the same reasoning gives a test its stop. A wall deadline fails a test the host
merely starved (eight bazel size timeouts in one gate, one of them a test that had passed), so a
test's stop is the CPU it spends: bound_cpu sets the process's RLIMIT_CPU and makes it raise a named
error. A test that idles spends no CPU and is not ended by this; bazel's own timeout is then only
the outermost guard.
"""

import resource
import signal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType

# CPU seconds a test process may spend, by the size its target declares: twice the wall seconds the
# size has always meant (small 60, medium 300, large 900, enormous 3600), so a test that spends its
# whole wall budget in CPU alone, on one core, still has room
CPU_BY_SIZE = {"small": 120, "medium": 600, "large": 1800, "enormous": 7200}
# CPU seconds after the soft stop that the kernel ends a process ignoring it
KILL_AFTER = 60
# the budget this process was given, once it has been
CPU_SET: list[int] = []


class CpuBudgetError(RuntimeError):
    """The test process spent its whole CPU budget: it is spinning, not starved."""


def budget_for(size: str) -> int:
    """Give the CPU seconds a test of this bazel size may spend.

    Args:
        size: The target's size (bazel's TEST_SIZE); anything unknown reads as medium.

    Returns:
        The CPU budget in seconds.

    """
    return CPU_BY_SIZE.get(size, CPU_BY_SIZE["medium"])


def over(_signum: int, _frame: FrameType | None) -> None:
    """Fail the running test, naming the CPU budget it spent (nemik:W1140).

    Raises:
        CpuBudgetError: Always.

    """
    message = (
        f"the test spent its CPU budget ({CPU_SET[0]} CPU seconds): it is spinning"
    )
    raise CpuBudgetError(message)


def bound_cpu(budget: int) -> None:
    """Limit the CPU this process may spend from now, and make the limit raise a named error.

    The soft limit raises SIGXCPU, which `over` turns into CpuBudgetError in the test's own thread;
    the hard limit, KILL_AFTER seconds later, ends a process that swallowed it. A limit can only
    fall once set, so the first call sets it and a later one changes nothing. A child process (a
    browser) inherits a limit of its own, and a busy host moves none of this: CPU time is not wall
    time.

    Args:
        budget: CPU seconds this process may spend from now.

    """
    if CPU_SET:
        return
    used = resource.getrusage(resource.RUSAGE_SELF)
    soft = int(used.ru_utime + used.ru_stime) + budget
    resource.setrlimit(resource.RLIMIT_CPU, (soft, soft + KILL_AFTER))
    signal.signal(signal.SIGXCPU, over)
    CPU_SET.append(budget)


def cpu_line(wall_s: float) -> str:
    """Say how much CPU this run used, in the shape the gate's per-target emit reads.

    Args:
        wall_s: How long the run took, in seconds.

    Returns:
        `shard cpu=S children=1 idle_wall=W`; CPU is this process plus its waited-for children.

    """
    own = resource.getrusage(resource.RUSAGE_SELF)
    kids = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = own.ru_utime + own.ru_stime + kids.ru_utime + kids.ru_stime
    return f"shard cpu={cpu:.1f}s children=1 idle_wall={wall_s:.1f}s"
