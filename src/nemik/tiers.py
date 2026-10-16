# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W600: the repo burn-down tiers, declared as data in rank-weights.toml [tiers].

The operator ordered the fleet's frontier by repo (2026-10-16, relayed by github-8f): the first
tier now, then later, then only when one blocks a priority repo, then lowest. This is a mark that
ordering and the view read, never a gate. This module only reads the declaration.
"""

import tomllib
from importlib.resources import files

ORDER = ["now", "later", "only-when-blocking", "lowest"]
UNLISTED = "unlisted"


def load(text: str | None = None) -> dict[str, str]:
    """Read each repo's tier.

    Args:
        text: The rank-weights TOML, or None for the one that ships with the package.

    Returns:
        The tier name by repo; empty when the table is absent. A repo named in two tiers keeps the
        earlier (more urgent) one.

    """
    if text is None:
        text = (
            files("nemik.data")
            .joinpath("rank-weights.toml")
            .read_text(encoding="utf-8")
        )
    document: dict[str, object] = tomllib.loads(text)
    table = document.get("tiers")
    found: dict[str, str] = {}
    if not isinstance(table, dict):
        return found
    for tier in ORDER:
        names = table.get(tier)
        if isinstance(names, list):
            for name in names:
                found.setdefault(str(name), tier)
    return found


def rank(tier: str) -> int:
    """Place a tier in the burn-down order.

    Args:
        tier: A tier name, or UNLISTED.

    Returns:
        0 for the first tier up to len(ORDER)-1 for the last; len(ORDER) for an unlisted repo.

    """
    return ORDER.index(tier) if tier in ORDER else len(ORDER)
