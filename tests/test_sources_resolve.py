# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W656: a wait on another source's card is resolved in the browser, or left as a stub."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

COMBINE = "docs => JSON.stringify(combine(docs))"
EDGE = '{"source":"urn:nemik:A/W1","target":"urn:nemik:B/W5","kind":"waits"}'


@pytest.fixture(scope="module")
def page() -> Iterator[Page]:
    """Open the view once for the module, so `combine` can be called on made-up documents.

    Yields:
        The page.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    with webpage.served() as url, sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                executable_path=str(Path(exe).resolve()) if exe else None
            )
        except PlaywrightError as e:
            pytest.skip(f"chromium unavailable: {e}")
        opened = browser.new_page(viewport={"width": 1700, "height": 1250})
        opened.goto(url)
        opened.wait_for_function(webpage.CY_READY, timeout=60000)
        yield opened
        browser.close()


def _node(repo: str, symbol: str, blocked_on: list[str]) -> dict[str, object]:
    """Build one card as a source publishes it.

    Args:
        repo: Its workstream.
        symbol: Its symbol.
        blocked_on: What it says it waits on.

    Returns:
        The node.

    """
    return {
        "id": f"urn:nemik:{repo}/{symbol}",
        "repo": repo,
        "symbol": symbol,
        "state": "blocked",
        "blocked_on": blocked_on,
    }


def _doc(
    nodes: list[dict[str, object]], edges: list[dict[str, str]]
) -> dict[str, object]:
    """Build one source's graph.

    Args:
        nodes: Its cards.
        edges: Its edges.

    Returns:
        The document.

    """
    return {"nodes": nodes, "edges": edges, "inbound": [], "operator": []}


def _combined(page: Page, docs: list[dict[str, object]]) -> str:
    """Combine documents in the page.

    Args:
        page: The page.
        docs: The sources' graphs.

    Returns:
        The combined graph as JSON text.

    """
    answer: object = page.evaluate(COMBINE, docs)
    return str(answer)


def test_a_wait_on_a_card_in_another_loaded_source_gets_an_edge(page: Page) -> None:
    """A:W1 waits on B:W5, which the second source holds: one waits edge joins them."""
    first = _doc([_node("A", "W1", ["B:W5"])], [])
    second = _doc([_node("B", "W5", [])], [])
    out = _combined(page, [first, second])
    assert EDGE in out
    assert '"state":"unloaded"' not in out


def test_a_wait_the_source_already_drew_is_not_drawn_twice(page: Page) -> None:
    """If the source resolved the wait itself, combining adds nothing."""
    drawn = {"source": "urn:nemik:A/W1", "target": "urn:nemik:B/W5", "kind": "waits"}
    first = _doc([_node("A", "W1", ["B:W5"])], [drawn])
    second = _doc([_node("B", "W5", [])], [])
    out = _combined(page, [first, second])
    assert out.count('"target":"urn:nemik:B/W5"') == 1


def test_a_wait_on_an_unloaded_source_becomes_a_stub(page: Page) -> None:
    """C is in no loaded source: the wait is drawn to a stub that carries the symbol."""
    first = _doc([_node("A", "W2", ["C:W9"])], [])
    second = _doc([_node("B", "W5", [])], [])
    out = _combined(page, [first, second])
    assert '"id":"urn:nemik:C/W9"' in out
    assert '"state":"unloaded"' in out
    assert '"cite":"C:W9"' in out
    assert '"source":"urn:nemik:A/W2","target":"urn:nemik:C/W9","kind":"waits"' in out


def test_a_wait_inside_its_own_repo_or_in_free_text_is_left_alone(page: Page) -> None:
    """W<n> and prose are the source's to resolve; only the repo:W<n> form crosses sources."""
    first = _doc([_node("A", "W1", ["W2", "waiting for the operator"])], [])
    second = _doc([_node("B", "W5", [])], [])
    out = _combined(page, [first, second])
    assert '"kind":"waits"' not in out
