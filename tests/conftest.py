# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""pytest hooks: the session's CPU line (nemik:W928) and Bazel's test shards (W1044)."""

import os
import sys
import time

import pytest
from cpuline import cpu_line

STARTED = time.monotonic()


def shard_of[T](items: list[T], total: int, index: int) -> list[T]:
    """Pick the share of the collected tests that one Bazel shard runs.

    Args:
        items: The collected tests, in collection order.
        total: How many shards the target runs in.
        index: This shard's number, from 0.

    Returns:
        Every `total`-th test starting at `index`, so slow tests that sit together spread out.

    """
    return [item for position, item in enumerate(items) if position % total == index]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Keep only this shard's tests when Bazel runs the target in several (nemik:W1044)."""
    total = int(os.environ.get("TEST_TOTAL_SHARDS", "1"))
    index = int(os.environ.get("TEST_SHARD_INDEX", "0"))
    items[:] = shard_of(items, total, index)


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Print the CPU line the gate's per-target series reads."""
    del session
    sys.stdout.write(cpu_line(time.monotonic() - STARTED) + "\n")
