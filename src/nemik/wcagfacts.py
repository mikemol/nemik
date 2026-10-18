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
RULE = re.compile(r"([^{}@]+)\{([^{}]*)\}")
NO_OUTLINE = re.compile(r"outline\s*:\s*(none|0)\b")
FOCUS = re.compile(r":focus(-visible)?\b")
# 1.4.1: the states the view colours, the table of label glyphs it prefixes, and the per-state
# cytoscape rules that set a border style or a shape.
STATES = [
    "ready",
    "working",
    "blocked",
    "done",
    "dropped",
    "unclaimed",
    "other",
    "interrupt",
]
STATE_MARKS = re.compile(r"const STATE_MARK = \{([^}]*)\}")
GLYPH = re.compile(r'(\w+):\s*"([^"]*)"')
NODE_RULE = re.compile(
    r'node\[(state|minted_during) = "(\w+)"\]\',\s*style:\s*\{([^{}]*)\}'
)
NON_COLOUR = ["border-style", "shape"]
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


def focus(html: str) -> dict[str, list[str]]:
    """Read how the page's stylesheet treats keyboard focus (WCAG 2.4.7).

    Args:
        html: The page's text.

    Returns:
        {"removed": selectors whose rule sets `outline: none` or `outline: 0`, "styled": the base
        selectors (focus pseudo-class stripped) of rules that style :focus or :focus-visible}. A
        selector is listed once per rule it appears in, in source order.

    """
    removed: list[str] = []
    styled: list[str] = []
    pairs: list[tuple[str, str]] = RULE.findall(html)
    for selectors, body in pairs:
        for selector in (s.strip() for s in selectors.split(",")):
            if FOCUS.search(selector):
                styled.append(FOCUS.sub("", selector).strip())
            elif NO_OUTLINE.search(body):
                removed.append(selector)
    return {"removed": removed, "styled": styled}


def marks(html: str) -> dict[str, list[str]]:
    """Read the marks, other than colour, that tell the view's card states apart (WCAG 1.4.1).

    Args:
        html: The page's text.

    Returns:
        {state: kinds} for every state the view colours: "glyph" when STATE_MARK gives it a label
        prefix, "border-style" or "shape" when a cytoscape rule for that state (or, for interrupt,
        for cards minted during an interrupt) sets one. A state with nothing is listed with [].
        A page with no STATE_MARK table draws no states, so it has nothing to judge: {}.

    """
    found: dict[str, list[str]] = {state: [] for state in STATES}
    table = STATE_MARKS.search(html)
    if not table:
        return {}
    glyphs: list[tuple[str, str]] = GLYPH.findall(table.group(1))
    for state, glyph in glyphs:
        if glyph.strip() and state in found:
            found[state].append("glyph")
    rules: list[tuple[str, str, str]] = NODE_RULE.findall(html)
    for key, value, body in rules:
        if value not in found or (key == "minted_during" and value != "interrupt"):
            continue
        for kind in NON_COLOUR:
            if f'"{kind}"' in body or f"{kind}:" in body:
                found[value].append(kind)
    return found


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
