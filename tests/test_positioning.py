# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W358: docs/positioning.md cannot drift from the tools.

Every nemik command it names is a console script of this package, every flag it pairs with a
command is one that command takes, and every workflow it names is modelled in data/workflows.toml.
"""

from __future__ import annotations

import inspect
import re
import tomllib
from pathlib import Path

from nemik import critical, history, rank

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "positioning.md").read_text()


def _scripts() -> set[str]:
    data: dict[str, dict[str, dict[str, str]]] = tomllib.loads(
        (ROOT / "pyproject.toml").read_text()
    )
    return set(data["project"]["scripts"])


def test_every_command_the_page_names_exists() -> None:
    """Every command the page names exists."""
    found: list[str] = re.findall(r"`(nemik-[a-z-]+)", DOC)
    named = set(found)
    assert named, "the page names no command"
    assert sorted(named - _scripts()) == []


def test_every_flag_the_page_gives_a_command_is_one_it_takes() -> None:
    """Every flag the page gives a command is one it takes."""
    parsers = {
        "nemik-rank": rank,
        "nemik-history": history,
        "nemik-critical": critical,
    }
    pairs: list[tuple[str, str]] = re.findall(r"`(nemik-[a-z-]+)[^`]*?(--[a-z-]+)", DOC)
    for command, flag in pairs:
        if command in parsers:
            source = Path(inspect.getfile(parsers[command])).read_text(encoding="utf-8")
            assert f'"{flag}"' in source, f"{command} takes no {flag}"


def test_every_workflow_the_page_names_is_modelled() -> None:
    """Every workflow the page names is modelled."""
    model: dict[str, list[dict[str, str]]] = tomllib.loads(
        (ROOT / "src/nemik/data/workflows.toml").read_text()
    )
    names = {w["name"] for w in model["workflow"]}
    cited_found: list[str] = re.findall(r"`workflow:([a-z-]+)`", DOC)
    cited = set(cited_found)
    assert cited, "the page names no workflow"
    assert sorted(cited - names) == []
