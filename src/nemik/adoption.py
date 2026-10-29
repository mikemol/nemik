# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Say whether each workstream runs mikemol-paths-forward from its own environment.

The operator's intent (2026-09-26): each repo installs the package as its own sha-pinned
dependency and executes it from its own .venv, not from mtools' tree. This reads each repo's
pyproject.toml and reports one of:

    declared        a dependency (project, optional or dependency-groups) on mikemol-pathsforward
    owner           the repo that ships the package (it contains its pyproject)
    missing         a pyproject.toml without that dependency
    no-pyproject    no pyproject.toml at all
    unobservable    a queue read from an export with no repo tree beside it (luthen's pod)
"""

from __future__ import annotations

import re
import tomllib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

PACKAGE = "mikemol-pathsforward"
_NAME = re.compile(r"^\s*([A-Za-z0-9._-]+)")


def _table(value: object) -> dict[str, object]:
    """Read a TOML value as a table, or as an empty one when it is anything else (nemik:W1253).

    Returns:
        The table's entries, keyed by string, or {} when the value is not a table.

    """
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def _names(specs: object) -> set[str]:
    out = set()
    for spec in specs if isinstance(specs, list) else []:
        if isinstance(spec, str) and (m := _NAME.match(spec)):
            out.add(m[1].lower().replace("_", "-"))
    return out


def adoption(queue_path: Path) -> str:
    """Return the adoption state of the repo holding `queue_path`.

    Returns:
        One of declared, owner, missing, no-pyproject or unobservable (see the module docstring).

    """
    if queue_path.parent.name != ".claude":
        return "unobservable"
    repo = queue_path.parents[1]
    for sub in repo.glob("*/pyproject.toml"):
        try:
            if tomllib.loads(sub.read_text()).get("project", {}).get("name") == PACKAGE:
                return "owner"
        except (OSError, tomllib.TOMLDecodeError):
            continue
    py = repo / "pyproject.toml"
    if not py.exists():
        return "no-pyproject"
    try:
        doc = tomllib.loads(py.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return "missing"
    project = _table(doc.get("project"))
    deps = _names(project.get("dependencies"))
    for group in _table(project.get("optional-dependencies")).values():
        deps |= _names(group)
    for group in _table(doc.get("dependency-groups")).values():
        deps |= _names(group)
    return "declared" if PACKAGE in deps else "missing"
