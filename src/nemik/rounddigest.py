# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2217: a digest of what the round depends on, so an unchanged queue is not ranked again.

The round export costs about a minute of CPU (luthen-observability, measured 2026-10-25), so a
trigger on every queue write is affordable only if a write that cannot change the round costs
nothing. The round reads, per card, its status, touches, vector, blocked_on, enables, manifest and
cause, and the landings document (it sets the round's width). This module folds exactly those into
one string; an evidence edit, a ledger line or a title does not move it.

The fold is FNV-1a over the UTF-8 bytes, kept in pure integer arithmetic: the digest is a change
detector, not a security boundary, and it must stay cheap to compute from the files alone. Paths
are taken as text and made into a Path inside, so the module imports nothing only for typing
(a TYPE_CHECKING import is a Codon wall: nemik:W2217).
"""

import json
from pathlib import Path

from nemik.queuefiles import QUEUE, workstream_files

FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
MASK = 0xFFFFFFFFFFFFFFFF
LIST_FIELDS = ("touches", "blocked_on", "enables", "manifest")
TEXT_FIELDS = ("symbol", "status", "vector", "caused_by")


def fold(text: str) -> int:
    """Fold a text into 64 bits (FNV-1a).

    Returns:
        The fold of the UTF-8 bytes of `text`.

    """
    value = FNV_OFFSET
    for byte in text.encode("utf-8"):
        value = ((value ^ byte) * FNV_PRIME) & MASK
    return value


def _words(value: object) -> str:
    """Spell a field the round reads: a list sorted and joined, a text as it is, none as empty.

    Returns:
        The field as one string.

    """
    if isinstance(value, list):
        return ",".join(sorted(str(v) for v in value))
    return "" if value is None else str(value)


def card_lines(repo: str, text: str) -> list[str]:
    """Spell the fields the round reads, one line per waypoint of a queue file.

    Returns:
        One line per waypoint, or one `unreadable` line when the text is not a queue.

    """
    document: object
    try:
        document = json.loads(text)
    except ValueError:
        return [f"{repo}|unreadable"]
    waypoints = document.get("waypoints") if isinstance(document, dict) else None
    if not isinstance(waypoints, list):
        return [f"{repo}|unreadable"]
    return [
        "|".join(
            [
                repo,
                *(_words(card.get(name)) for name in TEXT_FIELDS),
                *(_words(card.get(name)) for name in LIST_FIELDS),
            ]
        )
        for card in waypoints
        if isinstance(card, dict)
    ]


def digest(queues: list[tuple[str, str]], landings: str) -> str:
    """Digest every queue file and the landings document.

    Args:
        queues: (repo, the queue file's text) pairs.
        landings: The landings document's text, empty when there is none.

    Returns:
        Thirty-two hex digits: the fold of the queues' round-relevant lines, then the landings'.

    """
    lines = [line for repo, text in sorted(queues) for line in card_lines(repo, text)]
    return f"{fold(chr(10).join(lines)):016x}{fold(landings):016x}"


def queue_digest(root: str, landings: str) -> str:
    """Digest the queue files under the directory `root` and the landings file now.

    Returns:
        The digest; a missing landings file reads as empty.

    """
    queues = [
        (repo, path.read_text(encoding="utf-8"))
        for repo, path in workstream_files(Path(root), QUEUE)
    ]
    where = Path(landings)
    body = where.read_text(encoding="utf-8") if where.is_file() else ""
    return digest(queues, body)


def unchanged(fresh: str, digest_file: str) -> bool:
    """Say whether the digest kept in the file `digest_file` is `fresh`.

    Returns:
        True when the file exists and holds exactly that digest.

    """
    kept = Path(digest_file)
    return kept.is_file() and kept.read_text(encoding="utf-8").strip() == fresh


def remember(fresh: str, digest_file: str) -> None:
    """Keep `fresh` in the file `digest_file`, whole or not at all, so a reader never sees half."""
    kept = Path(digest_file)
    kept.parent.mkdir(parents=True, exist_ok=True)
    temporary = kept.with_suffix(".tmp")
    temporary.write_text(fresh + "\n", encoding="utf-8")
    temporary.replace(kept)


def inside(round_file: str, digest_file: str) -> bool:
    """Say whether the digest file would sit in the round file's directory tree.

    The round file's directory is the export tree the nemik pod reads whole, so a digest kept
    there would be served, and it covers the queues of repos the export refuses.

    Returns:
        True when the round file's directory is an ancestor of the digest file.

    """
    return Path(round_file).resolve().parent in Path(digest_file).resolve().parents
