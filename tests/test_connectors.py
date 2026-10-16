# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W584: the connector declaration reader holds the contract's required fields."""

import tomllib
from importlib.resources import files

import pytest

from nemik import connectors

TWO = """
[connectors.google-tasks]
id_scheme = "gtasks:{list}/{task}"
mode = "poll"
maps_to = "letters"
[connectors.google-tasks.credential]
scope = "tasks.readonly"
access = "read-only"
store = "pass:nemik/google-tasks"

[connectors.calendar]
id_scheme = "caldav:{uid}"
mode = "webhook"
maps_to = "writer-commands"
[connectors.calendar.credential]
scope = "calendar"
access = "read-write"
store = "file:~/.config/nemik/calendar-token"
"""


def _parse(text: str) -> list[connectors.Connector]:
    """Decode TOML text and read the connectors out of it.

    Args:
        text: A connectors declaration.

    Returns:
        The typed connectors.

    """
    document: dict[str, object] = tomllib.loads(text)
    return connectors.parse(document)


def test_two_connectors_parse_in_declared_order() -> None:
    """Both declarations come back typed, in the order the file gives them."""
    found = _parse(TWO)
    assert [c.name for c in found] == ["google-tasks", "calendar"]
    assert found[0].credential.access == "read-only"
    assert found[1].mode == "webhook"
    assert found[1].credential.store.startswith("file:")


def test_a_missing_credential_asks_the_operator_from_the_declaration() -> None:
    """The ask names the connector, store, scope and access, all from its declaration."""
    ask = connectors.credential_ask(_parse(TWO)[0])
    assert ask == (
        "operator: act put the google-tasks credential in pass:nemik/google-tasks "
        "(scope tasks.readonly, read-only)"
    )


def test_the_shipped_declaration_loads() -> None:
    """The file that ships with the package parses, whatever it declares so far."""
    text = files("nemik.data").joinpath("connectors.toml").read_text(encoding="utf-8")
    assert all(c.id_scheme for c in _parse(text))


@pytest.mark.parametrize(
    ("old", "new", "needle"),
    [
        ('mode = "poll"', 'mode = "push"', "mode must be one of"),
        ('access = "read-only"', 'access = "yes"', "access must be one of"),
        ('scope = "tasks.readonly"', 'scope = ""', "scope must be a non-empty string"),
        ('maps_to = "letters"', 'maps_to = "queue"', "maps_to must be one of"),
    ],
)
def test_an_incomplete_declaration_names_what_is_wrong(
    old: str, new: str, needle: str
) -> None:
    """Each required field is checked, and the error says which one failed."""
    with pytest.raises(connectors.DeclarationError, match=needle):
        _parse(TWO.replace(old, new, 1))


def test_a_declaration_without_a_credential_table_is_refused() -> None:
    """A connector that declares no credential cannot file its own operator ask."""
    text = '[connectors.x]\nid_scheme = "x:{id}"\nmode = "poll"\nmaps_to = "letters"\n'
    with pytest.raises(
        connectors.DeclarationError, match="credential table is required"
    ):
        _parse(text)


def test_no_connectors_table_is_refused() -> None:
    """A file with no connectors table is a mistake, not an empty set."""
    with pytest.raises(connectors.DeclarationError, match=r"no \[connectors\] table"):
        _parse("x = 1\n")
