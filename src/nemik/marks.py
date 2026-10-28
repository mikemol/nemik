# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W234/W236: read the verdict marks mtools' writer persists, never re-derive them privately.

The marks file is `.claude/paths-forward.marks.jsonl` beside the queue (mtools:W851, agreed in
mtools:W849/W852): append-only, one JSON object per transition, apart from the text ledger. A
record is {as_of, op, symbol, policy_version, input_digest, verdict}; `policy_version` is the
sha256 of the policy file that judged it and `as_of` is the same `now` the policy received.

A symbol with no mark is `derived`: judged now, because it was minted before the hook. A mark that
is older than the policy's `max_age_seconds`, or was judged by another policy, is `stale`: it is
printed as such and never read as current. An unreadable line is counted, not skipped silently.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, cast

from mikemol.pathsforward.opa_eval import POLICY

if TYPE_CHECKING:
    from pathlib import Path

    from mikemol.pathsforward.model import Json

MARKS = "paths-forward.marks.jsonl"
# The policy's own default (data.realizability_config.max_age_seconds, mtools:W850); a mark older
# than this is stale for the same reason a lapsed fact floors its gate.
MAX_AGE_SECONDS = 3600
MARK, DERIVED, STALE = "mark", "derived", "stale"


def _decoded(raw: str) -> object:
    """Decode one JSON line as an opaque value, so each caller narrows it.

    Returns:
        what json.loads read, typed as object.

    """
    return cast("object", json.loads(raw))


def policy_version() -> str:
    """Name the policy that judges now.

    Returns:
        the sha256 of the shipped realizability.rego, as the writer records it.

    """
    return hashlib.sha256(POLICY.read_bytes()).hexdigest()


def read(path: Path) -> tuple[dict[str, Json], int]:
    """Read the latest mark per symbol.

    Returns:
        (the latest mark for each symbol, the count of lines that were not a mark).

    """
    latest: dict[str, Json] = {}
    unreadable = 0
    if not path.is_file():
        return latest, unreadable
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            record = _decoded(raw)
        except json.JSONDecodeError:
            unreadable += 1
            continue
        if not isinstance(record, dict):
            unreadable += 1
            continue
        fields = cast("Json", record)
        symbol = fields.get("symbol")
        if not isinstance(symbol, str):
            unreadable += 1
            continue
        latest[symbol] = fields
    return latest, unreadable


def provenance(mark: Json | None, now: str, version: str) -> str:
    """Say where a verdict comes from.

    Returns:
        `derived` with no mark, `stale` for a lapsed or other-policy mark, else `mark`.

    """
    if mark is None:
        return DERIVED
    if mark.get("policy_version") != version:
        return STALE
    try:
        then = datetime.fromisoformat(str(mark.get("as_of")))
        age = (datetime.fromisoformat(now) - then).total_seconds()
    except (ValueError, TypeError):
        return STALE
    return STALE if age > MAX_AGE_SECONDS else MARK
