# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W645: the view's colour tokens come out per theme, dark falling back to light."""

from importlib.resources import files

from nemik.wcagfacts import tokens

SNIPPET = """
:root { --bg: #FFFFFF; --ink: #1d1d1b; --edge: #84847e; --gap: 4px; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #161615; --ink: #ecece8; }
}
"""


def test_light_tokens_are_the_root_block() -> None:
    """Hex values are lower-cased; a non-colour custom property is left out."""
    light = tokens(SNIPPET)["light"]
    assert light == {"--bg": "#ffffff", "--ink": "#1d1d1b", "--edge": "#84847e"}


def test_dark_overrides_and_falls_back_to_light() -> None:
    """--bg and --ink are overridden; --edge is not set by the dark block, so it keeps light's."""
    dark = tokens(SNIPPET)["dark"]
    assert dark == {"--bg": "#161615", "--ink": "#ecece8", "--edge": "#84847e"}


def test_a_page_without_a_root_block_has_no_tokens() -> None:
    """Nothing to judge is an empty answer for both themes."""
    assert tokens("<p>none</p>") == {"light": {}, "dark": {}}


def test_the_real_page_has_both_themes_with_the_same_names() -> None:
    """index.html declares colours for light and dark, and dark covers every light token."""
    html = files("nemik").joinpath("web/index.html").read_text(encoding="utf-8")
    found = tokens(html)
    assert found["light"]
    assert set(found["dark"]) == set(found["light"])
    assert found["dark"] != found["light"]
