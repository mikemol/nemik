"""nemik:W251: every recorded gap in the fleet, by card, for the flow model's residue demand.

The policy (mtools:W850) judges each live waypoint and returns its residue: the gaps it has not
closed, per gate. This gathers those entries across every workstream under `root`, keyed by
`repo:W<n>`, so `nemik.salience.audit` can inject demand at the cards that bear them.

An opa that is absent raises (`nemik.realize.verdicts`): a card that was not judged has no residue
recorded, and that must never read as a card with none.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from mikemol.pathsforward.lock import stamp

from nemik.check import QUEUE, workstream_files
from nemik.realize import verdicts

if TYPE_CHECKING:
    from pathlib import Path


def by_card(root: Path) -> dict[str, list[dict[str, object]]]:
    """Collect each judged card's residue entries.

    Returns:
        `repo:W<n>` to its residue entries, for every card that has any.

    """
    now = stamp(datetime.now(UTC))
    out: dict[str, list[dict[str, object]]] = {}
    for repo, path in workstream_files(root, QUEUE):
        for verdict in verdicts(repo, path, root, now):
            entries = verdict.get("residue")
            if isinstance(entries, list) and entries:
                out[str(verdict.get("ref"))] = [
                    e for e in entries if isinstance(e, dict)
                ]
    return out
