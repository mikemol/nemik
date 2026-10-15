# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W556: the run-row schema accepts one clean row and refuses the shapes W534 audited."""

import json
from pathlib import Path

import jsonschema

SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "nemik"
    / "data"
    / "run-row.schema.json"
)
CLEAN = {
    "ts": "2026-10-15T22:04:49Z",
    "run_id": "apply-set-main-20261015T220449Z",
    "trigger": "timer:apply-set",
    "exit": 0,
    "verdict": {"state": "applied", "planned": []},
    "detail": "three planned changes",
    "inputs_digest": "a" * 64,
}


def _errors(row: dict) -> list[str]:
    schema = json.loads(SCHEMA.read_text())
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    return [error.message for error in validator.iter_errors(row)]


def test_the_schema_is_itself_valid() -> None:
    """The file is a valid draft 2020-12 schema."""
    jsonschema.Draft202012Validator.check_schema(json.loads(SCHEMA.read_text()))


def test_a_clean_row_passes() -> None:
    """ts, run id, trigger, exit and an object verdict are enough."""
    assert _errors(CLEAN) == []


def test_apply_set_runs_as_audited_is_refused() -> None:
    """Its verdict is a string, and it has no run id, trigger or ts (it says when)."""
    row = {"set": "main", "exit": 0, "state": "applied", "verdict": "{}", "when": "x"}
    assert _errors(row)


def test_reaper_runs_as_audited_is_refused() -> None:
    """It has no timestamp, run id or trigger at all."""
    row = {"event": "verdict", "exit": 0, "set": "reaper", "verdict": {"state": "done"}}
    errors = _errors(row)
    assert any("'ts' is a required property" in e for e in errors)
    assert any("'run_id' is a required property" in e for e in errors)


def test_apply_ledger_as_audited_is_refused() -> None:
    """It spells the exit apply_exit, so exit is missing."""
    row = {"apply_exit": 0, "when": "2026-10-15T20:53:12Z", "root": "host"}
    assert any("'exit' is a required property" in e for e in _errors(row))


def test_a_string_verdict_is_refused() -> None:
    """A verdict is an object, not a JSON document in a string."""
    assert _errors({**CLEAN, "verdict": '{"state": "applied"}'})
