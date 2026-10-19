# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W706: the codemod leaves no wait_for_function call with a wall-clock bound."""

from webpage_waits import rewrite

BOUNDED = "page.wait_for_function(READY, timeout=60000)\n"
BARE = "page.wait_for_function(READY)\n"
MULTILINE = "page.wait_for_function(\n    '() => ready',\n    arg=1,\n)\n"
OTHER = "page.wait_for_selector('#x', timeout=500)\nx = {'timeout': 5}\n"


def test_a_timeout_value_becomes_zero() -> None:
    """The bound is replaced in place."""
    assert rewrite(BOUNDED) == "page.wait_for_function(READY, timeout=0)\n"


def test_a_call_without_one_gains_it() -> None:
    """A bare call gets timeout=0 after its last argument."""
    assert rewrite(BARE) == "page.wait_for_function(READY, timeout=0)\n"


def test_a_multiline_call_keeps_its_arguments() -> None:
    """A call split over lines gains timeout=0 after the trailing comma."""
    out = rewrite(MULTILINE)
    assert "arg=1," in out
    assert "timeout=0," in out
    assert out.count("wait_for_function") == 1


def test_nothing_else_is_touched() -> None:
    """Other calls and a plain dict with a timeout key stay as written."""
    assert rewrite(OTHER) == OTHER


def test_a_second_run_changes_nothing() -> None:
    """The rewrite is idempotent over every shape."""
    source = BOUNDED + BARE + MULTILINE + OTHER
    once = rewrite(source)
    assert rewrite(once) == once
