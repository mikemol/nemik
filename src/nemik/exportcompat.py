# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W635: derive a repo's version-2 export from its queue and luthen's version-1 list.

The compatible-first step of docs/withholding-at-source.md: until a repo's own writer emits its
export, nemik derives it, so the reader (nemik.exportv2) can be wired and tested against exactly
what the version-1 list withholds today.
"""

import json
from pathlib import Path

from nemik.exportv2 import VERSION


def derive(repo: str, symbols: list[str], withheld: set[str]) -> dict[str, object]:
    """Build the export a repo's policy would have produced.

    Args:
        repo: The repo.
        symbols: Every card symbol its queue holds.
        withheld: The refs (repo:W<n>) luthen's version-1 list withholds, for any repo.

    Returns:
        A version-2 export: the cards not withheld, whole by symbol, and the repo's withheld refs.

    """
    mine = sorted(r for r in withheld if r.startswith(f"{repo}:"))
    cards: list[dict[str, str]] = [
        {"symbol": s} for s in symbols if f"{repo}:{s}" not in withheld
    ]
    out: dict[str, object] = {
        "version": VERSION,
        "repo": repo,
        "cards": cards,
        "withheld": mine,
    }
    return out


def write(path: Path, export: dict[str, object]) -> None:
    """Write an export where the reader will look for it.

    Args:
        path: The export file.
        export: The document derive() built.

    """
    path.write_text(json.dumps(export, sort_keys=True), encoding="utf-8")
