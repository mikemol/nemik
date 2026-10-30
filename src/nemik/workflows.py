# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W320: nemik's workflows as data, for checking against skills/nemik/SKILL.md.

`data/workflows.toml` declares the card lifecycle, the rules the skill teaches and the
cross-workstream workflows. This module only reads it; tests/test_workflows.py is the correspondence
check.
"""

from __future__ import annotations

import tomllib
from importlib.resources import files
from typing import Any


def load(text: str | None = None) -> dict[str, Any]:
    """Load the workflow model; `text` overrides the packaged file (for tests).

    Returns:
        The parsed workflow model.

    """
    if text is None:
        text = files("nemik.data").joinpath("workflows.toml").read_text()
    return tomllib.loads(text)


def transitions(model: dict[str, Any]) -> list[dict[str, Any]]:
    """List the lifecycle's transitions.

    Returns:
        The transition tables of the workflow model.

    """
    return list(model["lifecycle"]["transition"])


def advice_only(model: dict[str, Any]) -> list[str]:
    """List what the skill teaches but nothing checks: lifecycle commands and unenforced rules.

    Returns:
        One entry per unenforced lifecycle command or rule.

    """
    loose = [
        f"{t['from']}->{t['to']} ({t['command']})"
        for t in transitions(model)
        if not t["enforced_by"]
    ]
    loose += [f"rule {r['id']}" for r in model["rule"] if not r["enforced_by"]]
    return loose
