# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W688: a card that throws warnings on the CLI carries a badge in the graph and its messages.

The operator (2026-10-18, 695f3e0a line 79877): a card with CLI warnings also carries a visual
indicator in the UI. The badge is ASCII after the card's symbol, "!" and the count ("!!" when one is
a Violation), so the count is the text and colour carries nothing; the messages are in Selected.
"""

import os
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

BADGES = """() => {
  const missing = [], stray = [];
  let carded = 0;
  cy.nodes('[symbol]').forEach(n => {
    const w = n.data('warnings') || [], label = n.data('label'), sym = n.data('symbol');
    const mark = w.some(x => x.severity === 'Violation') ? '!!' : '!';
    const want = w.length ? sym + mark + w.length : '';
    if (want) carded += 1;
    if (want && !label.includes(want)) missing.push(label);
    if (!want && /[0-9]!!?[0-9]/.test(label)) stray.push(label);
  });
  return missing.length || stray.length
    ? `missing ${JSON.stringify(missing)} stray ${JSON.stringify(stray)}` : `ok ${carded}`;
}"""

PANEL = """() => {
  const n = cy.nodes('[symbol]').filter(x => (x.data('warnings') || []).length)[0];
  const html = detailHTML(n.data());
  const first = n.data('warnings')[0];
  return html.includes('<dt>warnings</dt>') && html.includes(first.severity + ': ')
    ? 'ok' : html;
}"""


def _absolute(path: str) -> str:
    """Make a path absolute.

    Args:
        path: A path, possibly relative to the test's working directory.

    Returns:
        The absolute path.

    """
    return str(Path(path).resolve())


def _ask(script: str) -> str:
    """Run a script in the page over the fleet fixture once the graph is drawn.

    Args:
        script: A JavaScript function returning a string.

    Returns:
        What it returned.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    with webpage.served() as url, sync_playwright() as p:
        try:
            browser = p.chromium.launch(executable_path=_absolute(exe) if exe else None)
        except PlaywrightError as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(url)
        page.wait_for_function(webpage.CY_READY, timeout=60000)
        answer: object = page.evaluate(script)
        browser.close()
    return str(answer)


def test_each_card_with_warnings_shows_its_count_and_no_other_card_does() -> None:
    """Over the fleet fixture: every card with warnings has its badge after its symbol."""
    verdict = _ask(BADGES)
    assert verdict.startswith("ok "), verdict
    assert int(verdict.split()[1]) > 0, "the fixture fleet has no card with a warning"


def test_the_selected_panel_lists_the_warnings() -> None:
    """The detail view names the severity and the message of a card's warnings."""
    assert _ask(PANEL) == "ok"
