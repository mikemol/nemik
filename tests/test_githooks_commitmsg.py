# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W622: the commit-msg hook hands the message to mtools' trailer check, or refuses."""

import os
from pathlib import Path

from mikemol.hooks.waypoint_trailer import trailer_problem

HOOK = Path(__file__).parents[1] / ".githooks" / "commit-msg"
MESSAGE = "W1: subject\n\nbody\n\nWaypoint: W1\n\nCo-Authored-By: A <a@b.test>\n"


def test_the_hook_is_executable_and_names_the_checker() -> None:
    """It is a tracked executable script that execs the vendored trailer module."""
    text = HOOK.read_text(encoding="utf-8")
    assert os.access(HOOK, os.X_OK)
    assert text.startswith("#!/usr/bin/env bash")
    assert "mikemol.hooks.waypoint_trailer" in text
    assert 'exec "$python" -m mikemol.hooks.waypoint_trailer "$1"' in text


def test_a_missing_interpreter_refuses_the_commit() -> None:
    """The refusal path exists: an absent checker must not read as a pass."""
    text = HOOK.read_text(encoding="utf-8")
    assert "commit refused" in text
    assert "exit 1" in text


def test_the_interpreter_comes_from_the_real_checkout_when_one_is_named() -> None:
    """An isolated commit has a snapshot for $repo; the venv is in MIKEMOL_REAL_ROOT."""
    assert "${MIKEMOL_REAL_ROOT:-$repo}" in HOOK.read_text(encoding="utf-8")


def test_the_check_accepts_the_trailer_mikemol_commit_writes() -> None:
    """A message ending Waypoint: W<n> then a Co-Authored-By line passes."""
    assert trailer_problem(MESSAGE) is None
    assert trailer_problem(MESSAGE.replace("W1\n\nCo", "none\n\nCo")) is None


def test_the_check_refuses_a_message_with_no_or_a_malformed_trailer() -> None:
    """A plain git commit has none, and 'Waypoint: 174' reads like a citation but points nowhere."""
    assert trailer_problem("W1: subject\n\nbody\n") is not None
    assert trailer_problem("W1: subject\n\nWaypoint: 174\n") is not None
