# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W494: the 60 s poll follows the fleet in place instead of destroying the graph and laying it out again.

nemik-history --churn (W495) measured what a poll finds: structural changes (cards minted, closed,
rewired) are 76% of commits, a card's fields 20%, status flips 2%. So both are followed in place:
fields are written onto the cards that stay, new cards are placed beside what they are wired to,
removed ones leave their place empty, nothing already placed moves, and the layout says how far out
of date it is until the reader asks for it afresh.
"""

from collections.abc import Iterator

import pytest
import webpage
from playwright.sync_api import sync_playwright

# two animation frames on the page's own clock: whatever a change queued to draw has been drawn
TWO_FRAMES = (
    "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
)
POSITIONS = (
    "() => Object.fromEntries(cy.nodes().map(n => [n.id(), "
    "[n.position().x, n.position().y]]))"
)


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    with webpage.served() as url:
        yield url


def test_a_poll_that_only_changes_fields_follows_in_place(server: str) -> None:
    # W496: the poll rebuilt the graph whenever anything differed; a change to a card's fields now
    # writes onto the same graph: same instance, and nothing moves.
    with sync_playwright() as p:
        browser, page = webpage.launched_page(p, server)
        webpage.evaluate_value(page, "() => { cy.__kept = true; }")
        before = webpage.evaluate_text(page, POSITIONS)
        card = webpage.evaluate_value(
            page,
            "() => { const n = data.nodes.find(x => x.state === 'ready'"
            " && cy.getElementById(x.id).length);"
            " n.state = 'working'; n.title = 'retitled by a poll'; render(true); return n.id; }",
        )
        same = webpage.evaluate_value(page, "() => cy.__kept === true")
        after = webpage.evaluate_text(page, POSITIONS)
        label = webpage.evaluate_value(
            page, f"() => cy.getElementById({card!r}).data('label')"
        )
        hidden = webpage.evaluate_value(
            page, "() => document.getElementById('relayout').hidden"
        )
        browser.close()
    assert same is True, "the poll rebuilt the graph for a change to a card's fields"
    assert after == before, "a card moved"
    assert isinstance(label, str)
    assert "▸" in label
    assert hidden is True


ADD_A_CARD = """() => {
  const base = data.nodes.find(x => x.state === 'ready' && cy.getElementById(x.id).length);
  const n = structuredClone(base);
  n.id = base.id + '-polled'; n.symbol = 'W99999'; n.cite = base.cite + '-polled';
  n.title = 'added by a poll';
  data.nodes.push(n);
  data.edges.push({ source: n.id, target: base.id, kind: 'enables' });
  render(true);
  return n.id;
}"""

WHERE_IT_WENT = """(id) => {
  const n = cy.getElementById(id), box = n.parent();
  const clash = box.children().filter(m => m.id() !== id && m.isNode()).some(m => {
    const a = m.position(), b = n.position();
    return Math.abs(a.x - b.x) < (m.outerWidth() + n.outerWidth()) / 2
      && Math.abs(a.y - b.y) < (m.outerHeight() + n.outerHeight()) / 2;
  });
  return { there: n.length, finite: Number.isFinite(n.position().x), clash,
           kept: cy.__kept === true, hidden: document.getElementById('relayout').hidden,
           text: document.getElementById('relayout').textContent };
}"""

TAKE_IT_AWAY = """(id) => {
  data.nodes = data.nodes.filter(x => x.id !== id);
  data.edges = data.edges.filter(e => e.source !== id && e.target !== id);
  render(true);
  return { removed: cy.getElementById(id).length === 0, kept: cy.__kept === true,
           text: document.getElementById('relayout').textContent };
}"""

MOVED = """(before) => {
  const moved = [];
  cy.nodes().filter(n => !n.isParent()).forEach(n => {
    const b = before[n.id()];
    if (b && (b[0] !== n.position().x || b[1] !== n.position().y)) moved.push(n.id());
  });
  return moved;
}"""


def test_a_poll_that_adds_and_removes_cards_leaves_the_rest_where_it_was(
    server: str,
) -> None:
    # W498: a new card goes beside what it is wired to, a removed one leaves its place empty, and
    # the button lays the graph out afresh.
    with sync_playwright() as p:
        browser, page = webpage.launched_page(p, server)
        webpage.evaluate_value(page, "() => { cy.__kept = true; }")
        before = webpage.evaluate_value(page, POSITIONS)
        new_id = webpage.evaluate_value(page, ADD_A_CARD)
        added = webpage.evaluate_tree(page, WHERE_IT_WENT, new_id)
        moved = webpage.evaluate_text(page, MOVED, before)
        gone = webpage.evaluate_tree(page, TAKE_IT_AWAY, new_id)
        page.click("#relayout")
        webpage.until(page, "() => document.getElementById('relayout').hidden")
        fresh = webpage.evaluate_tree(
            page,
            "() => ({ rebuilt: cy.__kept !== true,"
            " hidden: document.getElementById('relayout').hidden })",
        )
        browser.close()
    assert webpage.whole(added, "there") == 1
    assert webpage.flag(added, "finite")
    assert not webpage.flag(added, "clash"), "the new card was placed on top of another"
    assert webpage.flag(added, "kept")
    assert not webpage.flag(added, "hidden")
    assert "1 cards" in added.string(added.root, "text")
    assert moved == "[]", f"cards moved: {moved[:200]}"
    assert webpage.flag(gone, "removed")
    assert webpage.flag(gone, "kept")
    assert "2 cards" in gone.string(gone.root, "text")
    assert webpage.flag(fresh, "rebuilt") and webpage.flag(fresh, "hidden"), (
        "re-layout did not start afresh"
    )


def test_a_rebuilt_card_list_keeps_the_focus_a_reader_had_in_it(server: str) -> None:
    # W480: a poll that changes a row's text rebuilds the list; keyboard focus stays on the same card.
    with sync_playwright() as p:
        browser, page = webpage.launched_page(p, server)
        webpage.evaluate_value(
            page, "() => { document.getElementById('sec-cards').open = true; }"
        )
        page.wait_for_selector("#cardlist button[tabindex='0']", state="attached")
        page.locator("#cardlist button[tabindex='0']").focus()
        page.keyboard.press("ArrowDown")
        page.keyboard.press("ArrowDown")
        held = webpage.evaluate_value(page, "() => document.activeElement.dataset.card")
        webpage.evaluate_value(
            page,
            "(id) => { const n = data.nodes.find(x => x.id !== id && x.symbol"
            " && cy.getElementById(x.id).length);"
            " n.title = 'retitled so the list rebuilds';"
            " n.state = n.state === 'ready' ? 'working' : 'ready'; render(true); }",
            held,
        )
        webpage.until(page, TWO_FRAMES)
        now = webpage.evaluate_value(page, "() => document.activeElement.dataset.card")
        stops = webpage.evaluate_value(
            page,
            "() => [...document.querySelectorAll('#cardlist button')]"
            ".filter(b => b.tabIndex === 0).length",
        )
        browser.close()
    assert now == held, "the list's rebuild dropped the reader's focus"
    assert stops == 1


def test_a_panel_whose_markup_did_not_change_is_not_rewritten(server: str) -> None:
    # W497: a panel the reader is scrolled or focused in is left alone by a poll that did not change it,
    # and one something else touched is painted again.
    with sync_playwright() as p:
        browser, page = webpage.launched_page(p, server)
        survived = webpage.evaluate_value(
            page,
            "() => { const box = document.getElementById('findings');"
            " box.firstElementChild.__kept = true; findings();"
            " return box.firstElementChild.__kept === true; }",
        )
        repainted = webpage.evaluate_value(
            page,
            "() => { const box = document.getElementById('findings');"
            " box.textContent = 'touched'; findings(); return box.textContent !== 'touched'; }",
        )
        browser.close()
    assert survived is True, "findings() rebuilt a panel that had not changed"
    assert repainted is True, "a panel something else touched was not repainted"
