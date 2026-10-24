# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W961: no module builds a dict with a spread, because the pinned Codon aborts on one.

W762 (2026-10-20) removed the construct from five modules and W960 (2026-10-24) from outbox,
whose spread made the Codon census abort in pairs on every gate run and page the host's
coredump alert. The census catches it only after the module is in a commit; this fails the
gate for the construct itself, so a new module cannot reintroduce it. `{**a, "k": v}` is an
ast.Dict with a None key.
"""

import ast
from importlib.resources import files
from pathlib import Path

PACKAGE = Path(str(files("nemik")))
# Modules that already carry a spread. Each one's Codon baseline entry is a clean parse error
# ("syntax error, unexpected ','"), not an abort. This list only shrinks: a module that stops
# spreading leaves it, and nothing joins it. (The first run of this test found history and rank
# beside calendars; a text search had found only calendars.)
ALLOWED = {"calendars.py", "history.py", "rank.py"}


def spreads(source: str) -> list[int]:
    """Find the dict displays that use a spread.

    Args:
        source: Python source text.

    Returns:
        The line of each `{**x, ...}`.

    """
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Dict) and None in node.keys
    ]


def test_the_walk_finds_a_spread_and_only_a_spread() -> None:
    """A spread is found; a dict built key by key, a call with keywords and update are not."""
    assert spreads('a = {**b, "k": 1}\n') == [1]
    assert spreads('x = 1\nc = {"k": 1, **d}\n') == [2]
    assert spreads('a = {"k": 1}\nb = dict(a, k=2)\nb.update(a)\nf(**a)\n') == []


def test_no_module_outside_the_allowlist_spreads_a_dict() -> None:
    """Every src/nemik module builds its dicts without a spread, except the allowlisted."""
    found = {
        path.name: lines
        for path in sorted(PACKAGE.glob("*.py"))
        if (lines := spreads(path.read_text(encoding="utf-8")))
        and path.name not in ALLOWED
    }
    assert found == {}, f"dict spread (Codon aborts; use dictops or update): {found}"


def test_the_allowlist_holds_only_modules_that_still_spread() -> None:
    """A module that stopped spreading is removed from the list, so the list only shrinks."""
    stale = [
        name
        for name in sorted(ALLOWED)
        if not spreads((PACKAGE / name).read_text(encoding="utf-8"))
    ]
    assert stale == [], f"no longer spreads, remove from ALLOWED: {stale}"
