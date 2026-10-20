# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W646: the Rego policy names a token pair under its WCAG bar; the real page meets them."""

from pagetext import page_text

from nemik.wcagjudge import judge

TEXT = "1.4.3"
COMPONENT = "1.4.11"
PAGE = """
:root {{ --bg: {bg}; --panel: {bg}; --ink: {ink}; --muted: {ink};
  --ready: {ink}; --working: {ink}; --blocked: {ink}; --other: {ink}; --interrupt: {ink};
  --unclaimed: {ink}; --edge: {ink}; --ring-fleet: {ink}; --ring-repo: {ink}; --ring-view: {ink}; }}
"""


def _page(bg: str, ink: str) -> str:
    """Build a page whose every token is bg or ink, in both themes (dark falls back to light).

    Args:
        bg: The background colour.
        ink: The colour of everything drawn on it.

    Returns:
        The page's CSS.

    """
    return PAGE.format(bg=bg, ink=ink)


def test_black_on_white_meets_every_bar() -> None:
    """21:1 passes both text and components, in both themes."""
    found = judge(_page("#ffffff", "#000000"))
    assert found["violations"] == []
    assert found["unjudged"] == []


def test_a_grey_on_white_text_pair_fails_1_4_3() -> None:
    """#bbbbbb on white is about 1.9:1: text and components both fall under their bars."""
    found = judge(_page("#ffffff", "#bbbbbb"))
    criteria = {str(v["criterion"]) for v in found["violations"]}
    assert criteria == {TEXT, COMPONENT}
    themes = {str(v["theme"]) for v in found["violations"]}
    assert themes == {"light", "dark"}


def test_a_mid_grey_passes_components_but_not_text() -> None:
    """#767676 on white is 4.54:1: it meets 4.5 for text, so nothing fails."""
    assert judge(_page("#ffffff", "#767676"))["violations"] == []
    failing = judge(_page("#ffffff", "#808080"))["violations"]
    assert {str(v["criterion"]) for v in failing} == {TEXT}


def test_a_token_the_page_lacks_is_reported_not_skipped() -> None:
    """A page with only --bg: every pair needing another token is unjudged."""
    found = judge(":root { --bg: #ffffff; }")
    assert found["unjudged"]
    assert found["violations"] == []


def test_the_real_page_meets_the_bars_it_declares() -> None:
    """The view's own tokens: the result is what the page does today, reported as it stands."""
    html = page_text()
    found = judge(html)
    assert found["unjudged"] == []
    assert found["violations"] == []
