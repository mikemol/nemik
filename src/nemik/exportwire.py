# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W634: the refs a fleet's per-repo exports withhold, ready for the static build.

Each repo's own export (nemik.exportv2) decides what leaves it. This reads every queue's card
symbols and asks the export in `exports/<repo>.json` for that repo's refs; a repo with no export
withholds all of its cards (fail closed per repo).
"""

import json
from pathlib import Path

from nemik.check import QUEUE, workstream_files
from nemik.exportv2 import export_refs


def repo_symbols(root: Path) -> dict[str, list[str]]:
    """Read the card symbols of every queue under a fleet root.

    Args:
        root: The fleet root.

    Returns:
        repo -> its card symbols; a queue that cannot be read gives no symbols.

    """
    out: dict[str, list[str]] = {}
    for repo, path in workstream_files(root, QUEUE):
        symbols: list[str] = []
        try:
            doc: object = json.loads(path.read_text(encoding="utf-8"))
        except OSError:
            out[repo] = symbols
            continue
        except ValueError:
            out[repo] = symbols
            continue
        # A dropped card (residue) is still a card the view shows, so it is withheld with the rest.
        for field in ("waypoints", "residue"):
            cards = doc.get(field) if isinstance(doc, dict) else None
            if isinstance(cards, list):
                for card in cards:
                    symbol: object = (
                        card.get("symbol") if isinstance(card, dict) else None
                    )
                    if isinstance(symbol, str):
                        symbols.append(symbol)
        out[repo] = symbols
    return out


def withheld_by_exports(root: Path, exports: Path) -> set[str]:
    """List the refs the per-repo exports under a directory withhold.

    Args:
        root: The fleet root.
        exports: A directory holding <repo>.json for each repo.

    Returns:
        The refs to withhold across every repo of the fleet.

    """
    out: set[str] = set()
    for repo, symbols in repo_symbols(root).items():
        out |= export_refs(repo, symbols, exports / f"{repo}.json")
    return out
