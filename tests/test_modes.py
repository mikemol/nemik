# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W727: the card list's order is a mode: rank by default, newest first on 2."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

# the symbol numbers of the list's top-level cards, in the order shown
ROOT_NUMBERS = """() => [...document.querySelectorAll('#cardlist > li > button[data-card]')]
  .map(b => Number(b.dataset.card.replace(/^.*\\/W/, '').replace(/\\D/g, '')))"""
DESCENDING = f"""() => {{
  const n = ({ROOT_NUMBERS})();
  return n.every((v, i) => i === 0 || n[i - 1] >= v);
}}"""
RADIO_ON = "(v) => document.querySelector(`input[name=listmode][value=${v}]`).checked"
PRESS_FROM_BODY = "() => document.activeElement.blur()"


@contextmanager
def _viewer() -> Generator[Page]:
    """Open the served fixture fleet in a watched page; skips without a browser.

    Yields:
        The page, ready.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    with webpage.served() as url, sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                executable_path=str(Path(exe).absolute()) if exe else None
            )
        except PlaywrightError as e:
            pytest.skip(f"chromium unavailable: {e}")
        try:
            page = browser.new_page(viewport={"width": 1700, "height": 1250})
            webpage.load(page, url, webpage.CY_READY)
            yield page
        finally:
            browser.close()


def test_two_orders_the_list_newest_first_and_one_restores_rank() -> None:
    """Key 2 sorts the top-level cards by descending symbol number; key 1 goes back."""
    with _viewer() as page:
        page.evaluate(PRESS_FROM_BODY)
        before: object = page.evaluate(ROOT_NUMBERS)
        page.keyboard.press("2")
        newest: object = page.evaluate(DESCENDING)
        newest_on: object = page.evaluate(RADIO_ON, "newest")
        page.keyboard.press("1")
        after: object = page.evaluate(ROOT_NUMBERS)
        rank_on: object = page.evaluate(RADIO_ON, "rank")
    assert newest is True
    assert newest_on is True
    assert rank_on is True
    assert after == before


CHAIN_DESCENDING = """() => {
  const n = [...document.querySelectorAll('#cardlist > li > button[data-card]')]
    .map(b => chainOf.get(b.dataset.card) || 0);
  return n.some(v => v > 0) && n.every((v, i) => i === 0 || n[i - 1] >= v);
}"""


def test_three_orders_the_list_by_the_longest_chain_beneath_each_card() -> None:
    """Key 3 puts the card with the longest chain of cards beneath it first."""
    with _viewer() as page:
        page.evaluate(PRESS_FROM_BODY)
        page.keyboard.press("3")
        ordered: object = page.evaluate(CHAIN_DESCENDING)
        on: object = page.evaluate(RADIO_ON, "critical")
    assert ordered is True
    assert on is True


REPOS_TOGETHER = """() => {
  const r = [...document.querySelectorAll('#cardlist > li > button[data-card]')]
    .map(b => String(cy.getElementById(b.dataset.card).data('repo')));
  return new Set(r).size > 1 && r.every((v, i) => i === 0 || r[i - 1].localeCompare(v) <= 0);
}"""


def test_four_groups_the_list_by_repo() -> None:
    """Key 4 lists each repo's cards together, the repos in name order."""
    with _viewer() as page:
        page.evaluate(PRESS_FROM_BODY)
        page.keyboard.press("4")
        together: object = page.evaluate(REPOS_TOGETHER)
        on: object = page.evaluate(RADIO_ON, "repo")
    assert together is True
    assert on is True


ROOT_HUMAN_FLAGS = """() => [...document.querySelectorAll('#cardlist > li > button[data-card]')]
  .map(b => cy.getElementById(b.dataset.card).data('blocked_kind') === 'human')"""
ASKS_FIRST = f"""() => {{
  const r = ({ROOT_HUMAN_FLAGS})();
  return r.some(v => v) && r.every((v, i) => i === 0 || r[i - 1] >= v);
}}"""
ANY_ASK = "() => cy.nodes('[symbol]').some(n => n.data('blocked_kind') === 'human')"


def test_five_puts_the_cards_waiting_on_the_operator_first() -> None:
    """Key 5 lists every card blocked on the operator before the others."""
    with _viewer() as page:
        any_ask: object = page.evaluate(ANY_ASK)
        if any_ask is not True:
            pytest.skip("the fixture fleet has no card waiting on the operator")
        page.evaluate(PRESS_FROM_BODY)
        page.keyboard.press("5")
        first: object = page.evaluate(ASKS_FIRST)
        on: object = page.evaluate(RADIO_ON, "asks")
    assert first is True
    assert on is True
