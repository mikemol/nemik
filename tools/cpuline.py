# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""cpuline: the line a test run prints so the gate can read its CPU (nemik:W928, W923).

mtools' mutants runner and rules_py/pytest_main print `shard cpu=S children=K idle_wall=W`, and the
gate's per-target series reads it (mtools:W1873, W1798): wall seconds move with host load, CPU does
not, so a test's cost, and what to split it into, is measured from CPU. tests/conftest.py prints it
when a pytest session ends.
"""

import resource


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
