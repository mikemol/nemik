# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1176: rank-weights.toml has a declared shape, and the file that ships satisfies it."""

import json
import tomllib
from pathlib import Path
from typing import cast

import jsonschema

DATA = Path(__file__).resolve().parents[1] / "src" / "nemik" / "data"
SCHEMA = DATA / "rank-weights.schema.json"
WEIGHTS = DATA / "rank-weights.toml"
REQUIRED = "is a required property"


def _weights() -> dict[str, object]:
    return cast("dict[str, object]", tomllib.loads(WEIGHTS.read_text(encoding="utf-8")))


def _errors(document: dict[str, object]) -> list[str]:
    """Collect what the schema refuses about a document.

    Returns:
        The first line of each refusal, empty when the document passes.

    """
    schema = cast("dict[str, object]", json.loads(SCHEMA.read_text(encoding="utf-8")))
    validator = jsonschema.Draft202012Validator(schema)
    return [str(error).splitlines()[0] for error in validator.iter_errors(document)]


def _without(key: str) -> dict[str, object]:
    return {k: v for k, v in _weights().items() if k != key}


def test_the_schema_is_itself_valid() -> None:
    """Validate checks the schema against its metaschema first, so it raises on a bad schema."""
    schema = cast("dict[str, object]", json.loads(SCHEMA.read_text(encoding="utf-8")))
    jsonschema.validate(_weights(), schema)


def test_the_shipped_weights_pass() -> None:
    """Every table the file declares today satisfies the schema."""
    assert _errors(_weights()) == []


def test_each_required_table_is_named_when_missing() -> None:
    """Dropping any one top-level key is refused, and the refusal names it."""
    for key in _weights():
        assert _errors(_without(key)) == [f"'{key}' {REQUIRED}"], key


def test_a_wrong_type_or_value_is_refused() -> None:
    """A string weight, an unknown model, an objective that is not one, a priority past 9."""
    health = cast("dict[str, object]", _weights()["health"])
    assert _errors({**_weights(), "local": "1"})
    order = cast("dict[str, object]", _weights()["order"])
    assert _errors({**_weights(), "order": {**order, "weight": "magic"}})
    assert _errors({**_weights(), "order": {**order, "tiers": [["colour"]]}})
    assert _errors({**_weights(), "ask_priority": {"40": 10}})
    assert _errors({**_weights(), "ask_priority": {"high": 1}})
    assert _errors({**_weights(), "health": {**health, "asks_owed": [5]}})


def test_a_key_the_schema_does_not_name_is_allowed() -> None:
    """A new section lands in the file before the schema learns it."""
    assert _errors({**_weights(), "forecast": {"days": 7}}) == []


def test_the_rules_a_schema_cannot_state() -> None:
    """A repo is in one burn-down tier at most; a health pair is [amber, red], red no lower."""
    tiers = cast("dict[str, list[str]]", _weights()["tiers"])
    repos = [repo for members in tiers.values() for repo in members]
    assert len(repos) == len(set(repos))
    health = cast("dict[str, list[float]]", _weights()["health"])
    assert all(amber <= red for amber, red in health.values())
