# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W859 (W785): history documents a host publishes and the server serves.

The history modes that read git (waits, forecast, score, events, density) cannot run in the
server, which may not spawn a process (W783). The host runs them and publishes each result as a
document, as nemik-hostroot does for the host-root frontier (W779); the server reads it back and
says how old it is. A document is its `as_of` stamp on the first line and the JSON body after it.

Everything here is plain text, so the Codon census compiles it (no datetime, no pathlib, no
`X | None`): the caller reads and writes the files and supplies the freshness cutoff as a stamp,
because a stamp of this fixed-width form sorts as text. A document that is absent, or whose first
line is not a stamp, reads as the empty pair, never as a guess. Only the modes named in MODES have
a document, so a request path never reaches another file.
"""

MODES = ("waits", "forecast", "score", "events", "density")
# a stamp, `d` for a digit: 2026-10-22T10:00:00Z
SHAPE = "dddd-dd-ddTdd:dd:ddZ"
STALE_HOURS = 26.0


def valid(stamp: str) -> bool:
    """Say whether text is exactly a stamp, `YYYY-MM-DDTHH:MM:SSZ`.

    Args:
        stamp: The text.

    Returns:
        True when every character has the shape's class: a digit where it has `d`, itself otherwise.

    """
    if len(stamp) != len(SHAPE):
        return False
    for at, want in enumerate(SHAPE):
        got = stamp[at]
        fits = got.isdigit() if want == "d" else got == want
        if not fits:
            return False
    return True


def file_name(mode: str) -> str:
    """Name the file a mode's document lives in.

    Args:
        mode: A history mode.

    Returns:
        `<mode>.json`, or the empty string for a name that is not one of MODES.

    """
    return f"{mode}.json" if mode in MODES else ""


def encode(now: str, body: str) -> str:
    """Make the text of a document.

    Args:
        now: The stamp of the time it was made.
        body: The JSON text the mode's function produced.

    Returns:
        The stamp, a newline and the body; empty when `now` is not a stamp, so nothing unreadable
        is ever written.

    """
    return f"{now}\n{body}" if valid(now) else ""


def decode(text: str) -> tuple[str, str]:
    """Split a document's text into its stamp and body.

    Args:
        text: What a document file holds.

    Returns:
        (as_of, body); both empty when the first line is not a stamp followed by a newline.

    """
    as_of, newline, body = text.partition("\n")
    if newline and valid(as_of):
        return as_of, body
    return "", ""


def stale(as_of: str, cutoff: str) -> bool:
    """Say whether a document is older than the freshness cutoff.

    Args:
        as_of: The document's stamp.
        cutoff: The stamp of the oldest time still fresh (now less STALE_HOURS).

    Returns:
        True when `as_of` is before `cutoff`, or is not a stamp: an unreadable age is never fresh.

    """
    return not valid(as_of) or as_of < cutoff


def wrap(mode: str, as_of: str, body: str, cutoff: str) -> str:
    """Wrap a document for the server, with its age, without parsing its body.

    Args:
        mode: One of MODES.
        as_of: The document's stamp.
        body: The published JSON text.
        cutoff: The stamp of the oldest time still fresh.

    Returns:
        JSON text `{"mode", "as_of", "stale", "rows"}`, `rows` being the body as published; empty
        for an unknown mode or a missing document (an empty `as_of`), so the route answers
        not-found and never a guess.

    """
    if not file_name(mode) or not valid(as_of):
        return ""
    flag = "true" if stale(as_of, cutoff) else "false"
    return f'{{"mode": "{mode}", "as_of": "{as_of}", "stale": {flag}, "rows": {body}}}'
