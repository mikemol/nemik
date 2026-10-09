"""nemik:W233: read luthen's host-apply export, the marks the host leaves on itself.

luthen-observability EXPORTS `host-apply.json` (luthen-observability:W665, `python -m
checks.host_apply_export`); nemik READS it and never writes or executes anything from it:

    {version: 1, as_of, kinds: {<kind>: {effect, restarts: [{unit, verb}]}},
     rows: [{id, activate: <kind>, after: [row ids], applied: {at, digest} | null}]}

- A row points at its kind, so "what replacing var-lib-rancher.mount restarts" is a walk: row, kind,
  units. The export carries no argv: those are root commands nemik never runs.
- `after` is EMPTY today because files.json states no ordering. An empty `after` is read as ordering
  UNKNOWN, never as independent, unless the export says otherwise (`ordering`): absent is not clean.
- `applied` is null when the live file does not equal its declared source, and also when the row
  could not be observed. Null is never read as applied.
- The export is a mark with an `as_of`: older than `MAX_AGE_SECONDS` it is stale, and a stale
  export proves nothing (the same decay as every other fact, nemik:W236).

A malformed export is reported in `problems`, not repaired and not silently partial.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from nemik.marks import MAX_AGE_SECONDS

if TYPE_CHECKING:
    from pathlib import Path

EXPORT = "host-apply.json"
# A waypoint cites a row as `host:<id>` (nemik:W256); the id is the row's key in the export.
HOST_REF = re.compile(r"host:([A-Za-z0-9][A-Za-z0-9._@-]*)")
EFFECTS = frozenset(
    {
        "install",
        "reload",
        "restart",
        "enable-timer",
        "start-heavy",
        "next-boot",
        "package",
        "tmpfiles",
        "other",
    }
)
VERBS = frozenset({"restart", "try-restart", "start", "enable-now", "reload"})
LUTHEN = "luthen-observability"
EXPORTER = "checks.host_apply_export"
EXPORTER_TIMEOUT_S = 60


@dataclass(frozen=True)
class Kind:
    """What activating one kind does: its effect class and the units it touches, in order."""

    effect: str
    restarts: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Row:
    """One declared host file: its kind, what it must follow, and whether the live file matches."""

    id: str
    activate: str
    after: tuple[str, ...]
    applied: tuple[str, str] | None


@dataclass(frozen=True)
class HostApply:
    """A parsed export. `problems` names everything that was malformed or inconsistent."""

    as_of: str
    kinds: dict[str, Kind]
    rows: dict[str, Row]
    ordering: str
    problems: tuple[str, ...] = field(default_factory=tuple)


def _dict(value: object) -> dict[str, object]:
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _kind(name: str, raw: object, problems: list[str]) -> Kind:
    body = _dict(raw)
    effect = str(body.get("effect"))
    if effect not in EFFECTS:
        problems.append(f"kind {name}: unknown effect {effect!r}")
    restarts: list[tuple[str, str]] = []
    for item in _list(body.get("restarts")):
        step = _dict(item)
        unit, verb = str(step.get("unit")), str(step.get("verb"))
        if verb not in VERBS:
            problems.append(f"kind {name}: unit {unit} has unknown verb {verb!r}")
        restarts.append((unit, verb))
    return Kind(effect, tuple(restarts))


def _row(raw: object, kinds: dict[str, Kind], problems: list[str]) -> Row | None:
    body = _dict(raw)
    ident = body.get("id")
    if not isinstance(ident, str) or not ident:
        problems.append("a row has no id")
        return None
    activate = str(body.get("activate"))
    if activate not in kinds:
        problems.append(f"row {ident}: activates unknown kind {activate!r}")
    applied = _dict(body.get("applied"))
    stamp = (str(applied.get("at")), str(applied.get("digest"))) if applied else None
    after = tuple(str(x) for x in _list(body.get("after")))
    return Row(ident, activate, after, stamp)


def parse(doc: object) -> HostApply:
    """Parse an export document.

    Returns:
        the export, with every malformed part named in `problems`.

    Raises:
        ValueError: when the document is not a version 1 export at all.

    """
    body = _dict(doc)
    if body.get("version") != 1:
        msg = f"not a host-apply export v1 (version {body.get('version')!r})"
        raise ValueError(msg)
    problems: list[str] = []
    kinds = {
        name: _kind(name, raw, problems)
        for name, raw in _dict(body.get("kinds")).items()
    }
    rows: dict[str, Row] = {}
    parsed: list[Row] = []
    for raw in _list(body.get("rows")):
        row = _row(raw, kinds, problems)
        if row is None:
            continue
        if row.id in rows:
            problems.append(f"row {row.id}: duplicate id")
        rows[row.id] = row
        parsed.append(row)
    for row in parsed:
        problems.extend(
            f"row {row.id}: after names unknown row {a}"
            for a in row.after
            if a not in rows
        )
    stated = body.get("ordering") != "none" and any(r.after for r in rows.values())
    return HostApply(
        str(body.get("as_of")),
        kinds,
        rows,
        "stated" if stated else "none",
        tuple(problems),
    )


def load(root: Path, *, run_exporter: bool = True) -> HostApply | None:
    """Read `<root>/host-apply.json`, else run luthen's exporter from its venv.

    The same two sources, in the same order, as nemik's liveness read (`nemik.wake.read_liveness`).
    `run_exporter=False` reads the file only: a survey runs on every command and must not start a
    subprocess.

    Returns:
        the export, or None when there is neither a file nor a runnable exporter.

    Raises:
        ValueError: when what was read is not a version 1 export.

    """
    path = root / EXPORT
    try:
        if path.exists():
            return parse(json.loads(path.read_text(encoding="utf-8")))
        luthen = root / LUTHEN
        python = luthen / ".venv" / "bin" / "python"
        if run_exporter and python.exists():
            done = subprocess.run(
                [str(python), "-m", EXPORTER],
                cwd=luthen,
                capture_output=True,
                text=True,
                check=True,
                timeout=EXPORTER_TIMEOUT_S,
            )
            return parse(json.loads(done.stdout))
    except (OSError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        msg = f"host-apply export unreadable: {exc}"
        raise ValueError(msg) from exc
    return None


def restarts_of(export: HostApply, row_id: str) -> list[tuple[str, str]]:
    """Walk row, kind, units: what activating this row touches.

    Returns:
        (unit, verb) in the export's order; empty for an unknown row or a kind that touches none.

    """
    row = export.rows.get(row_id)
    kind = export.kinds.get(row.activate) if row else None
    return list(kind.restarts) if kind else []


def effect_of(export: HostApply, row_id: str) -> str | None:
    """Name the effect class of a row's kind (`start-heavy` is what a hold must refuse).

    Returns:
        the effect, or None for an unknown row or kind.

    """
    row = export.rows.get(row_id)
    kind = export.kinds.get(row.activate) if row else None
    return kind.effect if kind else None


def fact(export: HostApply, row_id: str, now: str) -> dict[str, object] | None:
    """Give the witness fact for a row: `input.apply[<id>]` (nemik:W233).

    `applied` is true only when the row carries an applied mark AND the export is fresh AND
    well-formed; a null mark, an unknown kind or a stale export never read as applied.

    Returns:
        {applied, at, digest, as_of, stale}, or None when the row does not exist (an unresolved
        citation, never a pass).

    """
    row = export.rows.get(row_id)
    if row is None:
        return None
    try:
        age = (
            datetime.fromisoformat(now) - datetime.fromisoformat(export.as_of)
        ).total_seconds()
    except (ValueError, TypeError):
        age = float("inf")
    stale = age > MAX_AGE_SECONDS
    at, digest = row.applied if row.applied else (None, None)
    return {
        "applied": row.applied is not None and not stale and not export.problems,
        "at": at,
        "digest": digest,
        "as_of": export.as_of,
        "stale": stale,
    }
