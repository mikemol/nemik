# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W611: manifest drift and the files that keep riding along."""

from nemik.drift import drift, kind, ride_along


def test_a_file_outside_the_manifest_is_drift() -> None:
    """The manifest named two files; the commits touched a third."""
    touched = ["src/a.py", "tests/test_a.py", "ratchet/mutants.regex"]
    assert drift(touched, ["src/a.py", "tests/test_a.py"]) == ["ratchet/mutants.regex"]


def test_a_directory_entry_covers_what_is_under_it() -> None:
    """tests/ in the manifest names every file below it."""
    assert drift(["tests/x.py", "src/y.py"], ["tests/"]) == ["src/y.py"]


def test_drift_is_sorted_and_without_repeats() -> None:
    """A file touched by two commits is one drift entry."""
    assert drift(["b.py", "a.py", "b.py"], []) == ["a.py", "b.py"]


def test_a_kind_is_the_directory_or_the_basename() -> None:
    """tests/ for a test, the basename for a top-level file."""
    assert kind("tests/test_a.py") == "tests/"
    assert kind("src/nemik/a.py") == "src/nemik/"
    assert kind("BUILD.bazel") == "BUILD.bazel"


def test_ride_along_reports_only_what_enough_cards_missed() -> None:
    """tests/ was missed by two cards and BUILD.bazel by one: the bar of two keeps tests/."""
    drifts = [["tests/a.py", "BUILD.bazel"], ["tests/b.py"], []]
    assert ride_along(drifts, 2) == [("tests/", 2)]


def test_ride_along_orders_by_count_then_name() -> None:
    """Most cards first, ties by kind."""
    drifts = [["b.toml", "a.toml"], ["b.toml", "a.toml", "c.toml"], ["c.toml"]]
    assert ride_along(drifts, 1) == [("a.toml", 2), ("b.toml", 2), ("c.toml", 2)]
