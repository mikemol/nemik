"""nemik:W246: judge every live waypoint with mtools' realizability policy, in one batch.

The policy and its input envelope are mtools' (mtools:W850, shipped in the pinned pathsforward
wheel); this module only asks them about the whole queue instead of the symbols a caller names.
The queue is read through the adapter, the one module that calls `store.load`.

An opa that is absent, the wrong version or silent raises: a waypoint that was not judged has
measured nothing, so it never reads as clean.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mikemol.pathsforward import certify, inbound, opa_eval
from mikemol.pathsforward.model import text

from nemik.adapter import load_state

if TYPE_CHECKING:
    from pathlib import Path

    from mikemol.pathsforward.model import Json

_DONE = "done"


def verdicts(state_path: Path, root: Path, now: str) -> list[Json]:
    """Judge every waypoint that is not done.

    Returns:
        one verdict per waypoint, in queue order, each {ref, level, reference_arm, residue}.

    Raises:
        OpaUnavailableError: when opa is absent, is not the pinned version, or did not evaluate.

    """
    state = load_state(state_path)
    symbols = [text(w, "symbol") for w in state.waypoints if text(w, "status") != _DONE]
    built = certify.items(state, symbols, inbound.repo_name(state_path), now, root)
    return opa_eval.verdicts(built, opa_eval.resolve())
