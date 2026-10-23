# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""pytest hook: print the session's CPU line for the gate's per-target series (nemik:W928)."""

import sys
import time

import pytest
from cpuline import cpu_line

STARTED = time.monotonic()


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Print the CPU line the gate's per-target series reads."""
    del session
    sys.stdout.write(cpu_line(time.monotonic() - STARTED) + "\n")
