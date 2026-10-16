# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W568: `merged` is the dict display `{**base, **extra}`, written as a call for Codon."""

from nemik.dictops import merged


def test_it_equals_the_spread_display_including_key_order() -> None:
    """The base's keys come first in their order, then the extra's new keys."""
    base = {"b": 1, "a": 2}
    extra = {"c": 3, "d": 4}
    assert list(merged(base, extra).items()) == list({**base, **extra}.items())


def test_an_overridden_key_keeps_its_place() -> None:
    """A key in both takes the extra's value and stays where the base had it."""
    base = {"x": 1, "y": 2, "z": 3}
    result = merged(base, {"y": 9})
    assert list(result.items()) == [("x", 1), ("y", 9), ("z", 3)]


def test_neither_input_is_changed() -> None:
    """The result is a new dict; the base and the extra are left as they were."""
    base = {"a": 1}
    extra = {"b": 2}
    result = merged(base, extra)
    result["c"] = 3
    assert base == {"a": 1}
    assert extra == {"b": 2}
