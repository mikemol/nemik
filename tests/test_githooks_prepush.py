# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W621: the pre-push hook hands the push to the package's launcher, or refuses."""

import os
from pathlib import Path

HOOK = Path(__file__).parents[1] / ".githooks" / "pre-push"


def test_the_hook_is_executable_and_names_the_launcher() -> None:
    """It is a tracked executable script that execs mikemol-githook-pre-push."""
    text = HOOK.read_text(encoding="utf-8")
    assert os.access(HOOK, os.X_OK)
    assert text.startswith("#!/usr/bin/env bash")
    assert "mikemol-githook-pre-push" in text
    assert 'exec "$launcher" "$@"' in text


def test_a_missing_launcher_refuses_the_push() -> None:
    """The refusal path exists: an absent checker must not read as a pass."""
    text = HOOK.read_text(encoding="utf-8")
    assert "push refused" in text
    assert "exit 1" in text


def test_the_launcher_comes_from_the_real_checkout_when_one_is_named() -> None:
    """A push from an isolated commit's post-commit finds the launcher in MIKEMOL_REAL_ROOT."""
    assert "${MIKEMOL_REAL_ROOT:-$repo}" in HOOK.read_text(encoding="utf-8")
