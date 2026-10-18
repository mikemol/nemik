# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W645: the view's colour tokens in both themes, as the facts a WCAG policy judges.

The page declares its colours once, as custom properties on :root, with a prefers-color-scheme: dark
override of some of them. A policy (W646) judges contrast per theme, so this reads both and gives
the dark theme every token, falling back to the light value where the dark block does not set it.
"""

import math
import re

SHORT = 3
MAX_CHANNEL = 255
KNEE = 0.03928
TOKEN = re.compile(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\b")
LIGHT = re.compile(r":root\s*\{([^}]*)\}")
DARK = re.compile(
    r"@media\s*\(\s*prefers-color-scheme\s*:\s*dark\s*\)\s*\{\s*:root\s*\{([^}]*)\}"
)


def _tokens(block: str) -> dict[str, str]:
    """Read the hex colour custom properties of one CSS block.

    Args:
        block: The text between a rule's braces.

    Returns:
        name -> lower-case hex colour, for each custom property whose value is a hex colour.

    """
    pairs: list[tuple[str, str]] = TOKEN.findall(block)
    return {name: value.lower() for name, value in pairs}


def tokens(html: str) -> dict[str, dict[str, str]]:
    """Read the light and dark colour tokens from a page.

    Args:
        html: The page's text.

    Returns:
        {"light": {name: hex}, "dark": {name: hex}}; dark holds every token of light, overridden
        by the dark block where it sets one, and is empty when the page has no :root block.

    """
    found = LIGHT.search(html)
    light = _tokens(found.group(1)) if found else {}
    dark = dict(light)
    override = DARK.search(html)
    if override:
        dark.update(_tokens(override.group(1)))
    return {"light": light, "dark": dark}


def luminance(colour: str) -> float:
    """Measure a colour's WCAG relative luminance.

    Args:
        colour: A #rgb or #rrggbb colour.

    Returns:
        The relative luminance, 0.0 (black) to 1.0 (white).

    """
    digits = colour.lstrip("#")
    if len(digits) == SHORT:
        digits = "".join(c * 2 for c in digits)
    channels = [int(digits[i : i + 2], 16) / MAX_CHANNEL for i in (0, 2, 4)]
    lin = [
        c / 12.92 if c <= KNEE else math.pow((c + 0.055) / 1.055, 2.4) for c in channels
    ]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def facts(html: str) -> dict[str, dict[str, dict[str, float]]]:
    """Measure the page's colour tokens for a policy to judge.

    Args:
        html: The page's text.

    Returns:
        {theme: {token: {"lum": relative luminance}}} for the light and dark themes. Only hex
        colours of three or six digits are measured; a token of another form is left out.

    """
    return {
        theme: {
            name: {"lum": luminance(value)}
            for name, value in colours.items()
            if len(value) in {SHORT + 1, 2 * SHORT + 1}
        }
        for theme, colours in tokens(html).items()
    }
