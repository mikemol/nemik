# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W725: the card list is a tree: a card sits under the heaviest card it enables."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

ITEMS = "[...document.querySelectorAll('#cardlist button[data-card]')]"
LIST_IS_A_TREE = (
    "() => document.getElementById('cardlist').getAttribute('role') === 'tree'"
)
ALL_TREEITEMS = (
    f"() => {ITEMS}.length > 0"
    f" && {ITEMS}.every(b => b.getAttribute('role') === 'treeitem')"
)
SOME_NESTED = f"() => {ITEMS}.some(b => Number(b.getAttribute('aria-level')) > 1)"
PARENTS_FOLD = (
    "() => document.querySelectorAll('#cardlist button[aria-expanded]').length > 0"
)
STOPS = f"{ITEMS}.filter(b => !b.closest('[hidden]')).length"
FIRST_PARENT = "document.querySelector('#cardlist button[aria-expanded]')"
# fold the first row that has children, redraw the list
FOLD = f"""() => {{
  closedTree.add({FIRST_PARENT}.dataset.card);
  cardList();
}}"""
FOLDED_STATE = f"() => {FIRST_PARENT}.getAttribute('aria-expanded')"


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


def test_the_list_is_a_tree_of_treeitems_with_levels() -> None:
    """The list has role tree, every card is a treeitem, some sit under others, parents fold."""
    with _viewer() as page:
        tree: object = page.evaluate(LIST_IS_A_TREE)
        items: object = page.evaluate(ALL_TREEITEMS)
        nested: object = page.evaluate(SOME_NESTED)
        folds: object = page.evaluate(PARENTS_FOLD)
    assert tree is True
    assert items is True
    assert nested is True
    assert folds is True


def test_folding_a_parent_hides_its_children_from_the_stops() -> None:
    """A folded row reports aria-expanded false and its children are no longer stops."""
    with _viewer() as page:
        before: object = page.evaluate(f"() => {STOPS}")
        page.evaluate(FOLD)
        after: object = page.evaluate(f"() => {STOPS}")
        state: object = page.evaluate(FOLDED_STATE)
    assert isinstance(before, int)
    assert isinstance(after, int)
    assert after < before
    assert state == "false"
