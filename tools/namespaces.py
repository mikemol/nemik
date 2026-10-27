# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1150: which top-level package names the fleet's repos declare, and who else claims each.

linux-sources' namespace_collision.py found that three repos declared the one top-level name
`tools`: a venv holds one winner, and the loser's modules are simply absent, with no error at
install time or import time. Its scan reads the siblings of one tree. This reads every repo under
the fleet root and lists the names more than one declares.

A name is what a repo's pyproject.toml gives under [tool.setuptools] `packages = [...]` (the
top-level part of each entry). A pyproject that cannot be read is named as unread: its claims are
unknown, not absent, and a zero that cannot say what it read is not a zero. The reader takes the
quoted names of that one list by text and not through tomllib, so a pyproject it cannot find a
list in is read as declaring nothing, which the count says.

    python3 tools/namespaces.py [ROOT]
"""

import sys
from pathlib import Path

from nemik.check import default_root

SECTION = "tool.setuptools"


def quoted(chunk: str) -> list[str]:
    """Take the quoted strings out of a stretch of a TOML list.

    Returns:
        The strings between quotes, in order, either quote character.

    """
    parts = chunk.replace("'", '"').split('"')
    return [part for at, part in enumerate(parts) if at % 2 == 1]


def declared(text: str) -> list[str]:
    """Read the top-level package names a pyproject declares under [tool.setuptools] packages.

    Args:
        text: The pyproject.toml's text.

    Returns:
        The sorted top-level names (`a.b` is owned by whoever wins `a`); empty when it declares
        none.

    """
    names: list[str] = []
    in_section = collecting = False
    for line in text.splitlines():
        stripped = line.partition("#")[0].strip()
        if not collecting and stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped[1:-1].strip() == SECTION
            continue
        if in_section and not collecting and stripped.startswith("packages"):
            collecting = True
            stripped = stripped.partition("=")[2]
        if collecting:
            names.extend(quoted(stripped))
            collecting = "]" not in stripped
    return sorted({name.partition(".")[0] for name in names})


def census(root: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Read every repo under a root and collect who declares which name.

    Returns:
        (each name with the repos that declare it, the repos whose pyproject could not be read).

    """
    claims: dict[str, list[str]] = {}
    unread: list[str] = []
    for child in sorted(root.iterdir()):
        path = child / "pyproject.toml"
        if child.name.startswith(".") or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, ValueError):
            unread.append(child.name)
            continue
        for name in declared(text):
            claims.setdefault(name, []).append(child.name)
    return claims, unread


def report(claims: dict[str, list[str]], unread: list[str]) -> list[str]:
    """Write the census: the contested names, the count, and the repos not read.

    Returns:
        One line per contested name, then the totals, then each unread repo.

    """
    contested = sorted(name for name, repos in claims.items() if len(repos) > 1)
    lines = [f"{name}: claimed by {', '.join(claims[name])}" for name in contested]
    total = f"namespaces: {len(claims)} names declared, {len(contested)} contested"
    lines.append(total)
    lines.extend(f"unread (claims unknown, not absent): {repo}" for repo in unread)
    return lines


def main(argv: list[str]) -> int:
    """Print the fleet's package-name census.

    Returns:
        0.

    """
    root = Path(argv[0]) if argv else default_root()
    claims, unread = census(root)
    sys.stdout.write("\n".join(report(claims, unread)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
