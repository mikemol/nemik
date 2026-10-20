# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W658: WCAG 2.4.7: a rule that removes an outline needs a focus rule beside it."""

from pagetext import page_text

from nemik.wcagfacts import focus
from nemik.wcagjudge import judge

TOKENS = ":root { --bg: #ffffff; --ink: #000000; }"
CRITERION = "2.4.7"


def _focus_violations(css: str) -> list[str]:
    """Judge a stylesheet and name the selectors reported under 2.4.7.

    Args:
        css: The stylesheet's text.

    Returns:
        The selectors of the 2.4.7 violations.

    """
    found = judge(TOKENS + "\n" + css)["violations"]
    return [str(v["selector"]) for v in found if v.get("criterion") == CRITERION]


def test_facts_name_removed_and_styled_selectors() -> None:
    """A button with outline none is removed; a:focus-visible styles the base selector a."""
    css = "button { outline: none; } a:focus-visible { outline: 2px solid red; }"
    assert focus(css) == {"removed": ["button"], "styled": ["a"]}


def test_a_removed_outline_with_no_focus_rule_is_a_violation() -> None:
    """A button loses its outline and nothing replaces it."""
    assert _focus_violations("button { outline: none; }") == ["button"]


def test_a_focus_visible_rule_for_the_same_selector_replaces_it() -> None:
    """The outline is removed and :focus-visible styles the same base selector: no violation."""
    css = "button { outline: 0; } button:focus-visible { outline: 2px solid; }"
    assert _focus_violations(css) == []


def test_a_page_that_never_removes_an_outline_keeps_the_browsers_ring() -> None:
    """No outline rule at all: nothing is removed, nothing to report."""
    assert _focus_violations("button { color: red; }") == []


def test_the_real_page_removes_no_outline() -> None:
    """index.html: every focusable element keeps a visible focus indicator."""
    html = page_text()
    assert focus(html)["removed"] == []
    assert _focus_violations(html) == []
