# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Judge, from a parsed pyproject.toml, whether a workstream runs mikemol-paths-forward itself.

The operator's intent (2026-09-26): each repo installs the package as its own sha-pinned
dependency and executes it from its own .venv, not from mtools' tree. check.adoption_state reads
each repo's pyproject.toml and reports one of:

    declared        a dependency (project, optional or dependency-groups) on mikemol-pathsforward
    owner           the repo that ships the package (it contains its pyproject)
    missing         a pyproject.toml without that dependency
    no-pyproject    no pyproject.toml at all
    unobservable    a queue read from an export with no repo tree beside it (luthen's pod)

This module is the pure half (nemik:W1179): functions of a parsed document with builtin types and
no import, like nemik.tiers, so the Codon census can compile it. The file and TOML reads are
check.adoption_state's.
"""

PACKAGE = "mikemol-pathsforward"
NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"


def table(value: object) -> dict[str, object]:
    """Read a TOML value as a table, or as an empty one when it is anything else (nemik:W1253).

    Returns:
        The table's entries, keyed by string, or {} when the value is not a table.

    """
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def names(specs: object) -> set[str]:
    """Read the package names out of a list of requirement strings.

    A name is the leading run of letters, digits, dot, underscore and hyphen after any whitespace,
    lower-cased with underscores as hyphens; a spec that is not a string or has no name is skipped.

    Returns:
        The normalised names.

    """
    out: set[str] = set()
    if isinstance(specs, list):
        for spec in specs:
            if isinstance(spec, str):
                head = spec.lstrip()
                end = 0
                while end < len(head) and head[end] in NAME_CHARS:
                    end += 1
                if end:
                    out.add(head[:end].lower().replace("_", "-"))
    return out


def owns(document: dict[str, object]) -> bool:
    """Say whether a parsed pyproject is the one that ships the package.

    Returns:
        True when the project name is the package's.

    """
    return table(document.get("project")).get("name") == PACKAGE


def declares(document: dict[str, object]) -> bool:
    """Say whether a parsed pyproject depends on the package in any of its three places.

    Returns:
        True when the package is among the project, optional or dependency-group dependencies.

    """
    project = table(document.get("project"))
    deps = names(project.get("dependencies"))
    for group in table(project.get("optional-dependencies")).values():
        deps |= names(group)
    for group in table(document.get("dependency-groups")).values():
        deps |= names(group)
    return PACKAGE in deps
