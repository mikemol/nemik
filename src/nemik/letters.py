"""nemik:W271 (gcalculus:W224): is every letter in the inbox it is addressed to?

A letter is a file under `<repo>/inbox/`. Its first line says who wrote it and to whom
(`gcalculus → nemik: ...`, or with `->`). This reads the receiving side only: a letter whose header
names a recipient other than the inbox's owner is misdelivered, and one that names a repo that is
no workstream is unaddressable. A letter that was written and never put in any inbox cannot be seen
from here: nothing records that it was sent, so that witness needs a sender-side list.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

_HEADER = re.compile(
    r"^(?:#\s*)?([A-Za-z0-9][\w.-]*)\s*(?:→|->)\s*([A-Za-z0-9][\w.-]*)\s*[:(]"
)


class Letter(NamedTuple):
    inbox: str
    name: str
    sender: str
    recipient: str


def headers(root: Path) -> tuple[list[Letter], list[tuple[str, str]]]:
    """(addressed letters, [(inbox, file)] with no `from → to` header) under every `<repo>/inbox`."""
    addressed: list[Letter] = []
    unaddressed: list[tuple[str, str]] = []
    for path in sorted(root.glob("*/inbox/*.md")):
        inbox = path.parents[1].name
        first = next(
            (ln for ln in path.read_text(errors="replace").splitlines() if ln.strip()),
            "",
        )
        found = _HEADER.match(first.strip())
        if found:
            addressed.append(Letter(inbox, path.name, found[1], found[2]))
        else:
            unaddressed.append((inbox, path.name))
    return addressed, unaddressed


def misdelivered(letters: list[Letter], workstreams: set[str]) -> list[str]:
    """One line per letter whose recipient is not the inbox it sits in, or is no workstream."""
    out: list[str] = []
    for ltr in letters:
        if ltr.recipient != ltr.inbox:
            where = (
                f"belongs in {ltr.recipient}/inbox"
                if ltr.recipient in workstreams
                else f"names {ltr.recipient}, which is no workstream"
            )
            out.append(f"{ltr.inbox}/inbox/{ltr.name}: from {ltr.sender}; {where}")
    return out


def report(root: Path, workstreams: set[str]) -> tuple[list[str], int]:
    """Printable lines and the exit code: 0 clean, 5 when a letter is misdelivered."""
    addressed, unaddressed = headers(root)
    bad = misdelivered(addressed, workstreams)
    lines = [
        f"letters: {len(addressed)} addressed, {len(unaddressed)} without a header"
    ]
    lines += [f"MISDELIVERED {row}" for row in bad]
    return lines, 5 if bad else 0
