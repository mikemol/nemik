"""Does each workstream run mikemol-paths-forward from its own environment?

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
from pathlib import Path

PACKAGE = "mikemol-pathsforward"
_NAME = re.compile(r"^\s*([A-Za-z0-9._-]+)")


def _names(specs: object) -> set[str]:
    out = set()
    for spec in specs if isinstance(specs, list) else []:
        if isinstance(spec, str) and (m := _NAME.match(spec)):
            out.add(m[1].lower().replace("_", "-"))
    return out


def adoption(queue_path: Path) -> str:
    """The adoption state of the repo holding `queue_path`."""
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
    project = doc.get("project", {})
    deps = _names(project.get("dependencies"))
    for group in (project.get("optional-dependencies") or {}).values():
        deps |= _names(group)
    for group in (doc.get("dependency-groups") or {}).values():
        deps |= _names(group)
    return "declared" if PACKAGE in deps else "missing"
