# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W641: the per-prompt digest of nemik-check, with repeated Info rows collapsed.

The hook that injects the fleet reader's findings into every prompt printed one Info row per card
for shapes like ManifestShape ("ready leaf with no manifest": 101 rows, ~44 KB a turn). Warnings and
violations stay in full; an Info message that several cards share becomes one counted line, and the
full list stays behind nemik-check without --digest.
"""

Row = tuple[str, str, str]  # (severity, focus symbol, message)
# the header line a printed line sits under, and the line; a header is (line, "")
Keyed = tuple[str, str]

INFO = "Info"
SHARED = 2  # an Info message on this many cards or more is collapsed
INDENT = "  "  # nemik-check indents a finding under its repo's header line


def _keyed(lines: list[str]) -> list[Keyed]:
    """Pair each printed line with the header it sits under.

    A finding is indented and belongs to the nearest header above it (OK or VIOLATES and the repo,
    or a provenance line); a header is its own key. The same finding under another repo is another
    key.

    Returns:
        One (header, line) per line; (line, "") for a header.

    """
    out: list[Keyed] = []
    head = ""
    for line in lines:
        if line.startswith(INDENT):
            out.append((head, line))
        else:
            head = line
            out.append((line, ""))
    return out


def delta(lines: list[str], seen: list[str]) -> list[str]:
    """Keep only what changed since a digest a reader already saw (nemik:W766).

    A finding that is in `seen` under the same header is left out. A header is printed when it is
    new or when one of its findings is, so a shown finding keeps the repo it belongs to. The last
    line counts what was left out, and the full digest is the same command without --since.

    Args:
        lines: The digest as printed now.
        seen: The digest as printed when the reader last saw it; empty for a first sight.

    Returns:
        The changed lines, then one line counting the unchanged ones.

    """
    before = set(_keyed(seen))
    shown: list[str] = []
    printed = ""
    left = 0
    for key in _keyed(lines):
        head, line = key
        if key in before:
            left += 1
            continue
        if line and printed != head:
            shown.append(head)
            printed = head
        shown.append(line or head)
        if not line:
            printed = head
    note = "unchanged lines not shown (nemik-check --digest without --since)"
    shown.append(f"{left} {note}")
    return shown


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
