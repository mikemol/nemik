# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1176: the waypoint accessors read what json.loads reads, and match the schema's keys."""

import abc
import inspect
import json
from pathlib import Path
from typing import cast

import pytest

from nemik.tracker import parse_tree
from nemik.waypoint import FIELDS, TreeWaypoint, Waypoint, waypoints_of

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "src" / "nemik" / "data" / "waypoint.schema.json"
FLEET = ROOT / "tests" / "fixtures" / "fleet"
MANY = 100  # the fixtures hold far more cards than this
WAITED = 4  # the ticks the card in QUEUE has waited
QUEUE = (
    '{"waypoints": [{"symbol": "W1", "title": "t", "status": "blocked", "enables": ["W2", 3],'
    f' "blocked_on": ["x"], "blocked_kind": "agent", "ticks_blocked": {WAITED}}}]}}'
)


class Checked(abc.ABC):
    """The real abstract base: one abstract method per core field, as the plain interface cannot."""

    @abc.abstractmethod
    def symbol(self) -> str:
        """Name the symbol."""

    @abc.abstractmethod
    def title(self) -> str:
        """Name the title."""

    @abc.abstractmethod
    def status(self) -> str:
        """Name the status."""

    @abc.abstractmethod
    def enables(self) -> list[str]:
        """List what the card enables."""

    @abc.abstractmethod
    def blocked_on(self) -> list[str]:
        """List what the card waits on."""

    @abc.abstractmethod
    def blocked_kind(self) -> str:
        """Name who a block waits on."""


class Complete(TreeWaypoint, Checked):
    """The tree reader taken as the abstract base: it instantiates only if it overrides each."""


def _strings(value: object) -> list[str]:
    return [item for item in cast("list[object]", value) if isinstance(item, str)]


def test_the_accessors_read_a_card() -> None:
    """Each accessor gives the member's value; a non-string list item is left out."""
    (card,) = waypoints_of(QUEUE)
    assert card.symbol() == "W1"
    assert card.status() == "blocked"
    assert card.enables() == ["W2"]
    assert card.blocked_on() == ["x"]
    assert card.blocked_kind() == "agent"
    assert card.ticks_blocked() == WAITED


def test_an_absent_member_reads_empty() -> None:
    """A card with only a symbol reads "" and [] and 0, never raises."""
    (card,) = waypoints_of('{"waypoints": [{"symbol": "W9"}]}')
    assert (card.title(), card.status(), card.blocked_kind()) == ("", "", "")
    assert (card.enables(), card.blocked_on(), card.ticks_blocked()) == ([], [], 0)
    assert waypoints_of("{}") == []


def test_every_fixture_card_reads_the_same_through_the_tree_as_through_json() -> None:
    """The oracle: json.loads and the tree agree on hundreds of real cards from nineteen queues."""
    seen = 0
    for path in sorted(FLEET.glob("*/paths-forward.json")):
        text = path.read_text(encoding="utf-8")
        loaded = cast("dict[str, list[dict[str, object]]]", json.loads(text))
        for card, want in zip(waypoints_of(text), loaded["waypoints"], strict=True):
            assert card.symbol() == want["symbol"]
            assert card.title() == want["title"]
            assert card.status() == want["status"]
            assert card.enables() == _strings(want["enables"])
            assert card.blocked_on() == _strings(want["blocked_on"])
            assert card.blocked_kind() == (want.get("blocked_kind") or "")
            seen += 1
    assert seen > MANY


def test_the_accessors_are_the_schemas_core_keys() -> None:
    """Drift: every field the accessors name is in the schema, and every required key is named."""
    text = SCHEMA.read_text(encoding="utf-8")
    schema = cast("dict[str, dict[str, dict[str, object]]]", json.loads(text))
    core = schema["$defs"]["core"]
    declared = cast("dict[str, object]", core["properties"])
    required = cast("list[str]", core["required"])
    assert set(FIELDS) <= set(declared)
    assert set(required) <= set(FIELDS)


def test_a_real_abc_naming_each_field_is_implemented_by_the_tree_reader() -> None:
    """The abstract base names every field, and a tree reader is concrete under it."""
    assert inspect.isabstract(Checked)
    for name in FIELDS:
        assert hasattr(Checked, name), name
        assert hasattr(TreeWaypoint, name), name
    tree = parse_tree('{"waypoints": [{"symbol": "W3"}]}')
    at = tree.kids[tree.get(tree.root, "waypoints")][0]
    assert not inspect.isabstract(Complete)
    assert Complete(tree, at).symbol() == "W3"


def test_the_interface_refuses_to_answer() -> None:
    """The plain base class has no value of its own: each accessor raises NotImplementedError."""
    base = Waypoint()
    with pytest.raises(NotImplementedError):
        base.symbol()
    with pytest.raises(NotImplementedError):
        base.enables()
    with pytest.raises(NotImplementedError):
        base.ticks_blocked()
