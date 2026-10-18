# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W407: a compact OSLC resource preview for a card, as pure functions over plain values.

OSLC Core 3.0 Part 3 (resource preview): a resource advertises a Compact resource, a small
document with a title, a short title and a smallPreview, where the preview is {document,
hintWidth, hintHeight} and `document` names an HTML page the client embeds in an iframe. The
Compact resource is served as JSON with unprefixed keys (title, shortTitle, smallPreview, document,
hintWidth, hintHeight) and as Turtle; this module builds the JSON form and the small HTML document
it points at, from a card's cite, title, state and blockers. Nothing here reads a graph or touches
a file, so the same functions can serve a snapshot, a hover in the page, or a TRS reader that needs
a resource per card (nemik:W674).
"""

WIDTH = "320px"
HEIGHT = "72px"
ESCAPES = [("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;")]
OPEN = '<div class="oslc-preview"><b>'


def escape(text: str) -> str:
    """Make text safe to place in HTML.

    Args:
        text: Any text, a card's title for instance.

    Returns:
        The text with &, <, > and " replaced by their entities.

    """
    out = text
    for raw, entity in ESCAPES:
        out = out.replace(raw, entity)
    return out


def cite(repo: str, symbol: str) -> str:
    """Name a card the way the fleet cites it.

    Args:
        repo: The workstream.
        symbol: The card's symbol, W<n>.

    Returns:
        repo:W<n>.

    """
    return repo + ":" + symbol


def document_path(repo: str, symbol: str) -> str:
    """Say where a card's small preview document is published, relative to the export.

    Args:
        repo: The workstream.
        symbol: The card's symbol.

    Returns:
        preview/<repo>/<symbol>.html.

    """
    return "preview/" + repo + "/" + symbol + ".html"


def compact(base: str, repo: str, symbol: str, title: str) -> dict[str, object]:
    """Build a card's Compact resource in its JSON form.

    Args:
        base: The URL the export is served from, ending in /.
        repo: The workstream.
        symbol: The card's symbol.
        title: The card's title.

    Returns:
        title, shortTitle and a smallPreview naming the HTML document and its size hints.

    """
    small: dict[str, object] = {
        "document": base + document_path(repo, symbol),
        "hintWidth": WIDTH,
        "hintHeight": HEIGHT,
    }
    return {
        "title": cite(repo, symbol) + ": " + title,
        "shortTitle": cite(repo, symbol),
        "smallPreview": small,
    }


def preview_html(
    repo: str, symbol: str, title: str, state: str, blocked_on: list[str]
) -> str:
    """Build the small HTML document a client embeds for a card.

    Args:
        repo: The workstream.
        symbol: The card's symbol.
        title: The card's title.
        state: The card's state, ready, working, blocked or done.
        blocked_on: What the card says it waits on, as written.

    Returns:
        A self-contained fragment: the cite and title, the state, and the blockers when it has
        any. Every value is escaped.

    """
    head = OPEN + escape(cite(repo, symbol)) + "</b> " + escape(title)
    lines = [head, "<br>state: " + escape(state)]
    if blocked_on:
        lines.append("<br>blocked on: " + escape(", ".join(blocked_on)))
    lines.append("</div>")
    return "".join(lines)
