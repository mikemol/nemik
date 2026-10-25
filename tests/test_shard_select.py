# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1044: the shards of a target together run every test once, with slow neighbours apart."""

from conftest import shard_of

TESTS = [f"t{n}" for n in range(8)]


def test_the_shards_partition_the_tests_with_none_run_twice_or_lost() -> None:
    """Three shards cover all eight tests exactly once."""
    shards = [shard_of(TESTS, 3, index) for index in range(3)]
    assert sorted(item for shard in shards for item in shard) == sorted(TESTS)
    assert sum(len(shard) for shard in shards) == len(TESTS)


def test_neighbouring_tests_land_in_different_shards() -> None:
    """Every third test, so tests that sit together and cost alike are spread out."""
    assert shard_of(TESTS, 3, 0) == ["t0", "t3", "t6"]
    assert shard_of(TESTS, 3, 1) == ["t1", "t4", "t7"]


def test_one_shard_runs_everything() -> None:
    """The default, no sharding, is the whole list."""
    assert shard_of(TESTS, 1, 0) == TESTS
