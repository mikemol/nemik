# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W688: a card that throws warnings on the CLI carries a badge in the graph and its messages.

The operator (2026-10-18, 695f3e0a line 79877): a card with CLI warnings also carries a visual
indicator in the UI. The badge is ASCII after the card's symbol, "!" and the count ("!!" when one is
a Violation), so the count is the text and colour carries nothing; the messages are in Selected.
"""

import webpage
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


def _ask(script: str) -> str:
    """Run a script in the page over the fleet fixture once the graph is drawn.

    Args:
        script: A JavaScript function returning a string.

    Returns:
        What it returned.

    """
    with webpage.served() as url, sync_playwright() as p:
        # nemik:W846: launched_page names the requests that failed if the page breaks on load
        browser, page = webpage.launched_page(p, url)
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
