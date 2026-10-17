# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W627: which files a card's next step EDITS, as against files it only mentions.

luthen declared twelve --propose drafts unread and eleven were wrong: a next step names files it
reads or refers to ("see docs/x.md", "the shape in shapes.ttl") as readily as files it changes.
A path counts as edited when an editing verb stands before it in the same clause; every other path
in the text is only mentioned. Still a heuristic: the lines that use it say so (unverified).
"""

import re

PATH = re.compile(r"(?:[\w.-]+/)*[\w-]+\.(?:py|ttl|ya?ml|json|md|html|toml|js)\b")
VERB = re.compile(
    r"\b(?:edit|write|add|create|change|update|rewrite|move|delete|remove|replace|extend|port|"
    r"fix|split|rename|mint|emit|declare|teach|wire|swap|drop|raise|lower)\w*\b",
    re.IGNORECASE,
)
# a period inside a file name does not end a clause, one followed by space does
CLAUSE = re.compile(r"[;:\n]|\.(?=\s)")
REACH = 80  # characters before a path in which an editing verb counts


def edited_paths(text: str) -> list[str]:
    """List the files the text says it changes.

    Args:
        text: A card's next step.

    Returns:
        The distinct paths with an editing verb before them in the same clause, sorted.

    """
    found: set[str] = set()
    for match in PATH.finditer(text):
        before = text[max(0, match.start() - REACH) : match.start()]
        clause = CLAUSE.split(before)[-1]
        if VERB.search(clause):
            found.add(match.group(0))
    return sorted(found)
