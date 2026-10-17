# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W641: the per-prompt digest of nemik-check, with repeated Info rows collapsed.

The hook that injects the fleet reader's findings into every prompt printed one Info row per card
for shapes like ManifestShape ("ready leaf with no manifest": 101 rows, ~44 KB a turn). Warnings and
violations stay in full; an Info message that several cards share becomes one counted line, and the
full list stays behind nemik-check without --digest.
"""

Row = tuple[str, str, str]  # (severity, focus symbol, message)

INFO = "Info"
SHARED = 2  # an Info message on this many cards or more is collapsed


def collapse(rows: list[Row]) -> list[Row]:
    """Collapse the Info rows that share a message into one counted row.

    Args:
        rows: A repo's findings, as nemik-check prints them.

    Returns:
        The same rows, except an Info message carried by more than one card, which appears once at
        its first position as ("Info", "--", "<n> cards: <message>"). Other severities, and an
        Info message on one card, are unchanged.

    """
    counts: dict[str, int] = {}
    for sev, _, msg in rows:
        if sev == INFO:
            counts[msg] = counts.get(msg, 0) + 1
    out: list[Row] = []
    seen: set[str] = set()
    for sev, focus, msg in rows:
        n = counts.get(msg, 0) if sev == INFO else 0
        if n < SHARED:
            out.append((sev, focus, msg))
        elif msg not in seen:
            seen.add(msg)
            out.append((sev, "--", f"{n} cards: {msg}"))
    return out
