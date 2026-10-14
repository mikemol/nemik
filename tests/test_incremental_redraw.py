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

sync_api = pytest.importorskip("playwright.sync_api")

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
    with sync_api.sync_playwright() as p:
        browser, page = webpage.open_page(p, server)
        page.evaluate("() => { cy.__kept = true; }")
        before = page.evaluate(POSITIONS)
        card = page.evaluate(
            "() => { const n = data.nodes.find(x => x.state === 'ready'"
            " && cy.getElementById(x.id).length);"
            " n.state = 'working'; n.title = 'retitled by a poll'; render(true); return n.id; }"
        )
        same = page.evaluate("() => cy.__kept === true")
        after = page.evaluate(POSITIONS)
        label = page.evaluate(f"() => cy.getElementById({card!r}).data('label')")
        hidden = page.evaluate("() => document.getElementById('relayout').hidden")
        browser.close()
    assert same, "the poll rebuilt the graph for a change to a card's fields"
    assert after == before, "a card moved"
    assert "▸" in label
    assert hidden


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
    with sync_api.sync_playwright() as p:
        browser, page = webpage.open_page(p, server)
        page.evaluate("() => { cy.__kept = true; }")
        before = page.evaluate(POSITIONS)
        new_id = page.evaluate(ADD_A_CARD)
        added = page.evaluate(WHERE_IT_WENT, new_id)
        moved = page.evaluate(MOVED, before)
        gone = page.evaluate(TAKE_IT_AWAY, new_id)
        page.click("#relayout")
        page.wait_for_timeout(500)
        fresh = page.evaluate(
            "() => ({ rebuilt: cy.__kept !== true,"
            " hidden: document.getElementById('relayout').hidden })"
        )
        browser.close()
    assert added["there"] == 1 and added["finite"], added
    assert not added["clash"], "the new card was placed on top of another"
    assert added["kept"] and not added["hidden"] and "1 cards" in added["text"]
    assert moved == [], f"cards moved: {moved[:5]}"
    assert gone["removed"] and gone["kept"] and "2 cards" in gone["text"]
    assert fresh["rebuilt"] and fresh["hidden"], "re-layout did not start afresh"


def test_a_rebuilt_card_list_keeps_the_focus_a_reader_had_in_it(server: str) -> None:
    # W480: a poll that changes a row's text rebuilds the list; keyboard focus stays on the same card.
    with sync_api.sync_playwright() as p:
        browser, page = webpage.open_page(p, server)
        page.evaluate("() => { document.getElementById('sec-cards').open = true; }")
        page.wait_for_timeout(300)
        page.locator("#cardlist button[tabindex='0']").focus()
        page.keyboard.press("ArrowDown")
        page.keyboard.press("ArrowDown")
        held = page.evaluate("() => document.activeElement.dataset.card")
        page.evaluate(
            "(id) => { const n = data.nodes.find(x => x.id !== id && x.symbol"
            " && cy.getElementById(x.id).length);"
            " n.title = 'retitled so the list rebuilds';"
            " n.state = n.state === 'ready' ? 'working' : 'ready'; render(true); }",
            held,
        )
        page.wait_for_timeout(200)
        now = page.evaluate("() => document.activeElement.dataset.card")
        stops = page.evaluate(
            "() => [...document.querySelectorAll('#cardlist button')]"
            ".filter(b => b.tabIndex === 0).length"
        )
        browser.close()
    assert now == held, "the list's rebuild dropped the reader's focus"
    assert stops == 1


def test_a_panel_whose_markup_did_not_change_is_not_rewritten(server: str) -> None:
    # W497: a panel the reader is scrolled or focused in is left alone by a poll that did not change it,
    # and one something else touched is painted again.
    with sync_api.sync_playwright() as p:
        browser, page = webpage.open_page(p, server)
        survived = page.evaluate(
            "() => { const box = document.getElementById('findings');"
            " box.firstElementChild.__kept = true; findings();"
            " return box.firstElementChild.__kept === true; }"
        )
        repainted = page.evaluate(
            "() => { const box = document.getElementById('findings');"
            " box.textContent = 'touched'; findings(); return box.textContent !== 'touched'; }"
        )
        browser.close()
    assert survived, "findings() rebuilt a panel that had not changed"
    assert repainted, "a panel something else touched was not repainted"
