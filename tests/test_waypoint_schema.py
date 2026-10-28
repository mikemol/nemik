# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1176: the waypoint schema takes every card in the fleet's queues and refuses bad ones."""

import json
from pathlib import Path
from typing import cast

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "src" / "nemik" / "data" / "waypoint.schema.json"
FLEET = ROOT / "tests" / "fixtures" / "fleet"
CORE = ("symbol", "title", "status", "enables", "blocked_on")
EXPORTED = (*CORE, "blocked_kind")
REQUIRED = "is a required property"
MANY = 100  # the fixtures hold far more cards than this
CLEAN: dict[str, object] = {
    "symbol": "W7",
    "title": "Land the shape",
    "status": "ready",
    "enables": ["W9"],
    "touches": [],
    "blocked_on": [],
    "blocked_kind": None,
    "next_bounded_step": None,
    "evidence": "",
    "issued_at": "2026-10-28T00:00:00Z",
    "minted_during": "tick",
    "caused_by": None,
    "last_worked": "2026-10-28T00:00:00Z",
    "ticks_blocked": 0,
}


def _schema(*, full: bool) -> dict[str, object]:
    """Read the schema, or a root that points at its full form.

    Returns:
        The schema object.

    """
    loaded = cast("dict[str, object]", json.loads(SCHEMA.read_text(encoding="utf-8")))
    if full:
        return {"$ref": "#/$defs/full", "$defs": loaded["$defs"]}
    return loaded


def _errors(card: dict[str, object], *, full: bool = False) -> list[str]:
    """Collect what the schema refuses about a card.

    Returns:
        The first line of each refusal, empty when the card passes.

    """
    validator = jsonschema.Draft202012Validator(_schema(full=full))
    return [str(error).splitlines()[0] for error in validator.iter_errors(card)]


def _fleet_cards() -> list[tuple[str, dict[str, object]]]:
    cards: list[tuple[str, dict[str, object]]] = []
    for path in sorted(FLEET.glob("*/paths-forward.json")):
        document = cast("dict[str, object]", json.loads(path.read_text("utf-8")))
        rows = cast("list[object]", document["waypoints"])
        cards += [
            (path.parent.name, cast("dict[str, object]", row))
            for row in rows
            if isinstance(row, dict)
        ]
    return cards


def test_the_schema_is_itself_valid() -> None:
    """Validate checks the schema against its metaschema first, so it raises on a bad schema."""
    jsonschema.validate(CLEAN, _schema(full=False))
    jsonschema.validate(CLEAN, _schema(full=True))


def test_every_card_in_the_fleet_fixtures_passes() -> None:
    """Hundreds of published cards from nineteen queues satisfy the shared core."""
    cards = _fleet_cards()
    assert len(cards) > MANY
    bad = [(repo, card.get("symbol")) for repo, card in cards if _errors(card)]
    assert not bad, bad[:3]


def test_a_clean_full_card_passes_both() -> None:
    """The writer's own shape satisfies the core and the full form."""
    assert not _errors(CLEAN)
    assert not _errors(CLEAN, full=True)


def test_a_card_missing_a_core_key_is_refused() -> None:
    """All five core keys are required; blocked_kind is not, since a few older cards lack it."""
    for key in CORE:
        card = {k: v for k, v in CLEAN.items() if k != key}
        assert _errors(card) == [f"'{key}' {REQUIRED}"], key


def test_a_published_card_is_not_a_full_card() -> None:
    """The export's six keys pass the core and fail the full form, which says a key is missing."""
    slim = {k: CLEAN[k] for k in EXPORTED}
    assert not _errors(slim)
    assert any(REQUIRED in e for e in _errors(slim, full=True))


def test_a_declared_key_with_the_wrong_type_is_refused() -> None:
    """A status outside the five, a blocked_kind that is not agent or human, a string count."""
    assert _errors({**CLEAN, "status": "paused"})
    assert _errors({**CLEAN, "blocked_kind": "robot"})
    assert _errors({**CLEAN, "ticks_blocked": "3"})
    assert _errors({**CLEAN, "symbol": "7"})
