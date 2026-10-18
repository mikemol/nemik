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
    """Write an export where the reader will look for it, unless it is already there unchanged.

    Leaving an identical file alone keeps its modification time, which nemik-serve --publish uses
    to decide whether the exports changed; a rewrite every loop would rebuild the pod every loop.

    Args:
        path: The export file.
        export: The document derive() built.

    """
    text = json.dumps(export, sort_keys=True)
    try:
        if path.read_text(encoding="utf-8") == text:
            return  # unchanged: leave the file, and its modification time, alone (nemik:W636)
    except OSError:
        pass
    path.write_text(text, encoding="utf-8")
