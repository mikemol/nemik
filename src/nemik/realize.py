"""nemik:W246: judge every live waypoint with mtools' realizability policy, in one batch.

The policy and its input envelope are mtools' (mtools:W850, shipped in the pinned pathsforward
wheel); this module only asks them about the whole queue instead of the symbols a caller names.
The queue is read through the adapter, the one module that calls `store.load`.

An opa that is absent, the wrong version or silent raises: a waypoint that was not judged has
measured nothing, so it never reads as clean.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mikemol.pathsforward import certify, opa_eval
from mikemol.pathsforward.model import text

from nemik.adapter import load_state

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
        one verdict per waypoint, in queue order, each {ref, level, reference_arm, residue}.

    Raises:
        OpaUnavailableError: when opa is absent, is not the pinned version, or did not evaluate.

    """
    state = load_state(state_path)
    symbols = [text(w, "symbol") for w in state.waypoints if text(w, "status") != _DONE]
    built = certify.items(state, symbols, repo, now, root)
    return opa_eval.verdicts(built, opa_eval.resolve())


def rows(verdict: Json, source: str = "") -> list[str]:
    """Print one verdict as its coordinate line and one line per residue entry.

    The coordinate is the deepest gate closed with every gate before it clean; a residue entry
    names the gate it is at, what is missing and what would close it. Nothing is a bare reject.
    `source` says where the verdict came from (mark, derived or stale), when the caller knows.

    Returns:
        the lines.

    """
    residue = verdict.get("residue")
    entries = residue if isinstance(residue, list) else []
    head = f"{verdict.get('ref')}  {verdict.get('level')}  residue={len(entries)}"
    head += f"  ({source})" if source else ""
    lines = [head]
    for entry in entries:
        if isinstance(entry, dict):
            lines.append(
                f"    {entry.get('gate')}: {entry.get('what')}  [closes by: {entry.get('closes_by')}]"
            )
    return lines


def runtime_valid(verdict: Json) -> bool:
    """Report whether a waypoint is coverable with an empty residue.

    Returns:
        True when the verdict is the charter's runtime-valid.

    """
    return verdict.get("level") == _RUNTIME_VALID and not verdict.get("residue")
