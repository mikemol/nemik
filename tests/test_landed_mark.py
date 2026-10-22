# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W845: the landed status has a colour, a mark and a contrast check of its own."""

from pathlib import Path

from pagetext import page_text

POLICY = Path(__file__).resolve().parents[1] / "src" / "nemik" / "data" / "wcag.rego"
THEMES = 2  # the light token and the dark override


def test_landed_is_a_state_with_its_own_mark_and_legend_entry() -> None:
    """The state list names landed and its mark is a glyph no other state or role uses."""
    text = page_text()
    assert '"ready", "working", "blocked", "landed", "done"' in text
    assert 'landed: "^ "' in text
    assert text.count(': "^ "') == 1  # this role only


def test_landed_has_a_colour_in_both_themes() -> None:
    """The light token and the dark override each define --landed."""
    assert page_text().count("--landed:") == THEMES


def test_landed_is_judged_for_contrast_against_the_panel() -> None:
    """The WCAG policy lists --landed among the components that need 3:1 against the panel."""
    policy = POLICY.read_text(encoding="utf-8")
    assert '{"fg": "--landed", "bg": "--panel"}' in policy
