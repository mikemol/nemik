# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W600: the repo burn-down tiers, declared as data in rank-weights.toml [tiers].

The operator ordered the fleet's frontier by repo (2026-10-16, relayed by github-8f): the first
tier now, then later, then only when one blocks a priority repo, then lowest. This is a mark that
ordering and the view read, never a gate. This module only reads the declaration.
"""

ORDER = ["now", "later", "only-when-blocking", "lowest"]
UNLISTED = "unlisted"


def parse(document: dict[str, object]) -> dict[str, str]:
    """Read each repo's tier from a parsed rank-weights document.

    Reading and parsing the TOML file is rank.load_tiers(), so this module needs no file or TOML
    import and is a pure function of the document it is given.

    Args:
        document: The parsed rank-weights TOML.

    Returns:
        The tier name by repo; empty when the table is absent. A repo named in two tiers keeps the
        earlier (more urgent) one.

    """
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


def of_cite(cite: str, declared: dict[str, str]) -> str:
    """Name the tier of the repo a citation points into.

    Args:
        cite: A `<repo>:W<n>` citation.
        declared: The tiers by repo, from load().

    Returns:
        The repo's tier, or UNLISTED.

    """
    return declared.get(cite.partition(":")[0], UNLISTED)


def of_row(row: dict[str, object], declared: dict[str, str]) -> str:
    """Name the tier of the repo an ask row's `ref` points into.

    Args:
        row: A row carrying a `ref` citation.
        declared: The tiers by repo, from load().

    Returns:
        The repo's tier, or UNLISTED.

    """
    return of_cite(str(row["ref"]), declared)


def order(
    rows: list[dict[str, object]], category: str, declared: dict[str, str]
) -> list[int]:
    """Pick a category's rows and place them by tier, most urgent first.

    Args:
        rows: Ask rows carrying a `category` and a `ref` citation.
        category: The category to keep.
        declared: The tiers by repo, from load().

    Returns:
        The indexes of the kept rows, stably sorted by their repo's tier, so their given order holds
        inside a tier.

    """
    kept = [i for i, row in enumerate(rows) if row["category"] == category]
    keys = {i: rank(of_row(rows[i], declared)) for i in kept}
    return sorted(kept, key=keys.__getitem__)


def rank(tier: str) -> int:
    """Place a tier in the burn-down order.

    Args:
        tier: A tier name, or UNLISTED.

    Returns:
        0 for the first tier up to len(ORDER)-1 for the last; len(ORDER) for an unlisted repo.

    """
    return ORDER.index(tier) if tier in ORDER else len(ORDER)
