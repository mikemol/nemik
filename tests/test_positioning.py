# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W358: docs/positioning.md cannot drift from the tools. Every nemik command it names is a
console script of this package, every flag it pairs with a command is one that command takes, and every
workflow it names is modelled in data/workflows.toml.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "positioning.md").read_text()


def _scripts() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return set(data["project"]["scripts"])


def test_every_command_the_page_names_exists() -> None:
    named = set(re.findall(r"`(nemik-[a-z-]+)", DOC))
    assert named, "the page names no command"
    assert sorted(named - _scripts()) == []


def test_every_flag_the_page_gives_a_command_is_one_it_takes() -> None:
    from nemik import critical, history, rank

    parsers = {
        "nemik-rank": rank.main,
        "nemik-history": history.main,
        "nemik-critical": critical.main,
    }
    for command, flag in re.findall(r"`(nemik-[a-z-]+)[^`]*?(--[a-z-]+)", DOC):
        if command in parsers:
            source = Path(parsers[command].__code__.co_filename).read_text()
            assert f'"{flag}"' in source, f"{command} takes no {flag}"


def test_every_workflow_the_page_names_is_modelled() -> None:
    model = tomllib.loads((ROOT / "src/nemik/data/workflows.toml").read_text())
    names = {w["name"] for w in model["workflow"]}
    cited = set(re.findall(r"`workflow:([a-z-]+)`", DOC))
    assert cited, "the page names no workflow"
    assert sorted(cited - names) == []
