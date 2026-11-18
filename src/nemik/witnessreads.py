# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2284: the fact references a Rego witness reads, found without a parser.

A witness reads the world through nemik's fixed observers (`input.git_ref["nemik@abc"].exists`,
`input.promql["up"].values[0]`): an observer, a quoted key, and a field. Two things need to know
which a witness reads: the `--on` filter (evaluate only the witnesses that read a fact that just
landed, W2285) and the check that warns on a field no observer produces (W2263, which found nine
landed cards carrying a field that never existed). Plain string scanning, no regular expression and
no parser, so the module compiles under the pinned Codon like the observers it describes.

A key is a Rego string, so it is either interpreted (double quotes, with backslash escapes) or raw
(backticks, no escapes): a PromQL key full of quotes is where an author reaches for the raw form.
"""

PREFIX = "input."
INTERPRETED = '"'
RAW = "`"


class UnclosedKeyError(Exception):
    """A key whose closing quote is not in the text."""


def _word(text: str, at: int) -> str:
    """Read the identifier that starts at `at`.

    Returns:
        The letters, digits and underscores from `at`, empty when none start there.

    """
    end = at
    while end < len(text) and (text[end].isalnum() or text[end] == "_"):
        end += 1
    return text[at:end]


def _key(text: str, at: int, quote: str) -> tuple[str, int]:
    """Read a key that starts at `at` (just after the opening quote).

    A double-quoted key undoes its escaped quotes and backslashes; a backtick key is raw and ends
    at the next backtick.

    Returns:
        The key and the index of the closing quote.

    Raises:
        UnclosedKeyError: When the closing quote is not in the text.

    """
    out = ""
    pos = at
    while pos < len(text):
        char = text[pos]
        if quote == INTERPRETED and char == "\\" and pos + 1 < len(text):
            out += text[pos + 1]
            pos += 2
            continue
        if char == quote:
            return out, pos
        out += char
        pos += 1
    raise UnclosedKeyError(text[at:])


def refs(text: str) -> list[tuple[str, str, str]]:
    """Name every fact a Rego witness reads through an observer's quoted key.

    Returns:
        One (observer, key, field) per `input.OBSERVER["KEY"]` or `input.OBSERVER[`KEY`]` in the
        text, in reading order; the field is the identifier after `].` and is empty when the
        reference stops at the bracket. `input.now`, a reference without a bracketed key and a key
        that never closes are not facts and are left out.

    """
    found: list[tuple[str, str, str]] = []
    at = text.find(PREFIX)
    while at >= 0:
        following = text.find(PREFIX, at + len(PREFIX))
        pos = at + len(PREFIX)
        observer = _word(text, pos)
        pos += len(observer)
        quote = text[pos + 1 : pos + 2]
        if observer and text[pos : pos + 1] == "[" and quote in {INTERPRETED, RAW}:
            try:
                key, close = _key(text, pos + 2, quote)
            except UnclosedKeyError:
                at = following
                continue
            if text[close + 1 : close + 2] == "]":
                field = ""
                if text[close + 2 : close + 3] == ".":
                    field = _word(text, close + 3)
                found.append((observer, key, field))
        at = following
    return found
