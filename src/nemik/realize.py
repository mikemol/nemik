# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W246: judge every live waypoint with mtools' realizability policy, in one batch.

The policy and its input envelope are mtools' (mtools:W850, shipped in the pinned pathsforward
wheel); this module only asks them about the whole queue instead of the symbols a caller names.
The queue is read through the adapter, the one module that calls `store.load`.

An opa that is absent, the wrong version or silent raises: a waypoint that was not judged has
measured nothing, so it never reads as clean.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from mikemol.pathsforward import certify, opa_eval
from mikemol.pathsforward.lock import stamp
from mikemol.pathsforward.model import text

from nemik.adapter import load_state
from nemik.residue import by_card

if TYPE_CHECKING:
    from pathlib import Path

    from mikemol.pathsforward.model import Json

_DONE = "done"
_RUNTIME_VALID = "coverable"


def verdicts(repo: str, state_path: Path, root: Path, now: str) -> list[Json]:
    """Judge every waypoint that is not done.

    `repo` names the workstream, as nemik's survey does: a queue in the export layout
    (`<repo>/paths-forward.json`) has no `.claude` directory to read the name from.

    Returns:
        one verdict per waypoint, in queue order, each {ref, level, reference_arm, residue}. An
        OpaUnavailableError from the judge propagates when opa is absent, is not the pinned
        version, or did not evaluate.

    """
    state = load_state(state_path)
    symbols = [text(w, "symbol") for w in state.waypoints if text(w, "status") != _DONE]
    built = certify.items(state, symbols, certify.Where(repo, root), now)
    return opa_eval.verdicts(built, opa_eval.resolve())


def judged(files: list[tuple[str, Path]], root: Path) -> list[dict[str, object]]:
    """Judge every queue a caller names, each verdict as a plain dict (nemik:W1659).

    The list of queue files is passed in because this module cannot import nemik.check (which
    imports it): metrics and rank each name the fleet's queues themselves.

    Returns:
        One verdict per judged card, each {ref, level, reference_arm, residue}. An opa that is
        absent raises (`verdicts`), so a card that was not judged never reads as one with no gaps.

    """
    now = stamp(datetime.now(UTC))
    return [
        dict(verdict)
        for repo, path in files
        for verdict in verdicts(repo, path, root, now)
    ]


def residue_gaps(
    files: list[tuple[str, Path]], root: Path
) -> dict[str, list[dict[str, object]]]:
    """Collect every recorded gap in the named queues, by card (nemik:W251, W1659).

    Returns:
        `repo:W<n>` to its residue entries, for every judged card that has any; an opa that is
        absent raises.

    """
    return by_card(judged(files, root))


def rows(verdict: Json, source: str = "") -> list[str]:
    """Print one verdict as its coordinate line and one line per residue entry.

    The coordinate is the deepest gate closed with every gate before it clean; a residue entry
    names the gate it is at, what is missing and what would close it. Nothing is a bare reject.
    `source` says where the verdict came from (mark, derived or stale), when the caller knows.

    Returns:
        the lines.

    """
    residue = verdict.get("residue")
    no_entries: list[object] = []
    entries = residue if isinstance(residue, list) else no_entries
    head = f"{verdict.get('ref')}  {verdict.get('level')}  residue={len(entries)}"
    head += f"  ({source})" if source else ""
    lines = [head]
    lines.extend(
        f"    {entry.get('gate')}: {entry.get('what')}"
        f"  [closes by: {entry.get('closes_by')}]"
        for entry in entries
        if isinstance(entry, dict)
    )
    return lines


def runtime_valid(verdict: Json) -> bool:
    """Report whether a waypoint is coverable with an empty residue.

    Returns:
        True when the verdict is the charter's runtime-valid.

    """
    return verdict.get("level") == _RUNTIME_VALID and not verdict.get("residue")
