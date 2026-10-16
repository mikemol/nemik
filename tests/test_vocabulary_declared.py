# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W529: every nemik: term the code emits or reads is declared in nemik.ttl."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USED = re.compile(r"\bNEMIK\.([A-Za-z][A-Za-z0-9]*)\b")
DECLARED = re.compile(r"^nemik:([A-Za-z][A-Za-z0-9]*)\s", re.MULTILINE)
# a name with no vocabulary meaning: a throwaway in a docstring or a test double
NOT_TERMS = {"x"}


def _names(pattern: re.Pattern[str], text: str) -> set[str]:
    """Collect what a pattern's one group matches in a text.

    Args:
        pattern: A regex with one capture group.
        text: The text to search.

    Returns:
        The captured names.

    """
    return {match.group(1) for match in pattern.finditer(text)}


def _used() -> set[str]:
    """Collect the NEMIK.<term> names used across the package.

    Returns:
        The term names.

    """
    found: set[str] = set()
    for path in (ROOT / "src" / "nemik").glob("*.py"):
        found |= _names(USED, path.read_text(encoding="utf-8"))
    return found - NOT_TERMS


def test_every_term_the_code_uses_is_declared() -> None:
    """A term used in code but absent from nemik.ttl is vocabulary nobody can look up."""
    text = (ROOT / "src" / "nemik" / "data" / "nemik.ttl").read_text(encoding="utf-8")
    missing = sorted(_used() - _names(DECLARED, text))
    assert not missing, f"undeclared in nemik.ttl: {', '.join(missing)}"
