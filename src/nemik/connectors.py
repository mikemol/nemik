# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W584: the declaration every connector makes, as typed records.

A connector is one inbound or outbound integration (nemik:W371). What it must say about itself is
data, not code: the scheme of the source ids it dedupes by, the credential it needs (scope,
whether read-only, where it is stored), whether it polls or takes webhooks, and what it maps to
(letters, or printed writer commands). The conformance test (W585) and the missing-credential ask
(W586) both read these records, so neither has to know a connector's internals.

The module takes the table already decoded from data/connectors.toml and does no I/O, so it
imports nothing Codon lacks (the census, nemik:W560, holds it compiling); the reader that decodes
the file belongs to the caller.
"""

MODES = ["poll", "webhook"]
MAPS_TO = ["letters", "writer-commands"]
ACCESS = ["read-only", "read-write"]


class Credential:
    """Where a connector's secret lives and what it may do with it.

    A plain annotated class with an explicit __init__: the one form that runs identically under
    CPython and Codon (nemik:W567, option A), so it has no generated __eq__ and no frozen.
    """

    scope: str
    access: str
    store: str

    def __init__(self, scope: str, access: str, store: str) -> None:
        """Hold the three facts.

        Args:
            scope: What the credential may touch.
            access: read-only or read-write; a choice, not a boolean (nemik:W569).
            store: Where it is kept.

        """
        self.scope = scope
        self.access = access
        self.store = store


class Connector:
    """One connector's declaration, in the shared Python and Codon class form."""

    name: str
    id_scheme: str
    credential: Credential
    mode: str
    maps_to: str

    def __init__(
        self, name: str, id_scheme: str, credential: Credential, mode: str, maps_to: str
    ) -> None:
        """Hold the declaration.

        Args:
            name: The connector's name.
            id_scheme: The scheme of the source ids it dedupes by.
            credential: Its credential.
            mode: poll or webhook.
            maps_to: letters or writer-commands.

        """
        self.name = name
        self.id_scheme = id_scheme
        self.credential = credential
        self.mode = mode
        self.maps_to = maps_to


class DeclarationError(ValueError):
    """A connector declaration that does not say what the contract requires."""


def _text(table: dict[str, object], key: str, where: str) -> str:
    """Read a required non-empty string.

    Args:
        table: The table that should hold the key.
        key: The key.
        where: The connector's name, for the error.

    Returns:
        The string.

    Raises:
        DeclarationError: When the key is missing, not a string, or empty.

    """
    value = table.get(key)
    if not isinstance(value, str) or not value:
        message = f"connector {where}: {key} must be a non-empty string"
        raise DeclarationError(message)
    return value


def _choice(table: dict[str, object], key: str, where: str, allowed: list[str]) -> str:
    """Read a required string that must be one of a fixed set.

    Args:
        table: The table that should hold the key.
        key: The key.
        where: The connector's name, for the error.
        allowed: The accepted values.

    Returns:
        The string.

    Raises:
        DeclarationError: When it is not one of the allowed values.

    """
    value = _text(table, key, where)
    if value not in allowed:
        options = ", ".join(allowed)
        message = f"connector {where}: {key} must be one of {options}, not {value}"
        raise DeclarationError(message)
    return value


def _credential(table: dict[str, object], where: str) -> Credential:
    """Read the credential sub-table.

    Args:
        table: The connector's table.
        where: The connector's name, for the error.

    Returns:
        The typed credential.

    Raises:
        DeclarationError: When the table is absent or a field is missing or not an allowed value.

    """
    sub = table.get("credential")
    if not isinstance(sub, dict):
        message = f"connector {where}: a credential table is required"
        raise DeclarationError(message)
    return Credential(
        scope=_text(sub, "scope", where),
        access=_choice(sub, "access", where, ACCESS),
        store=_text(sub, "store", where),
    )


def parse(document: dict[str, object]) -> list[Connector]:
    """Read the connectors out of a decoded declaration.

    Args:
        document: The decoded connectors.toml, with one [connectors.<name>] table per connector.

    Returns:
        The connectors, in the order declared.

    Raises:
        DeclarationError: When the connectors table is absent or any declaration is incomplete.

    """
    connectors = document.get("connectors")
    if not isinstance(connectors, dict):
        message = "no [connectors] table"
        raise DeclarationError(message)
    found: list[Connector] = []
    for name, table in connectors.items():
        if not isinstance(table, dict):
            message = f"connector {name}: must be a table"
            raise DeclarationError(message)
        found.append(
            Connector(
                name=str(name),
                id_scheme=_text(table, "id_scheme", str(name)),
                credential=_credential(table, str(name)),
                mode=_choice(table, "mode", str(name), MODES),
                maps_to=_choice(table, "maps_to", str(name), MAPS_TO),
            )
        )
    return found
