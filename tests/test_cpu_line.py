# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W928: a test run prints the CPU line in the shape the gate's per-target emit reads."""

import re

from cpuline import cpu_line


def test_the_cpu_line_has_the_shape_the_gate_reads() -> None:
    """The gate parses `shard cpu=S children=K idle_wall=W`."""
    line = cpu_line(12.34)
    assert re.fullmatch(r"shard cpu=\d+\.\d+s children=1 idle_wall=12\.3s", line), line
