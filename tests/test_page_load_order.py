# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1069: which name the page errors with when late scripts are lost is pinned, in a browser.

docs/page-test-happens-before.md argues that when the scripts after the sixth are refused (a server
that went away mid-load), the page's first error is `popLater is not defined`, because the inline
script evaluates popLater (index.html line 192) before any other name from them. That rested on
reading the page, and a line scan of it proved unreliable (strings, templates, arrows). These tests
run the page and refuse those requests, so a later edit that moves a load-time use earlier changes
the name here instead of silently changing the failure's signature.
"""

from importlib.resources import files
from pathlib import Path

from webpage import first_error

SIXTH = 6  # Chromium fetches six at once; these follow the first six
LATE = ("viewstate.js", "panels.js", "cards.js", "wasm.js")
OTHERS = ("viewstate.js", "panels.js", "wasm.js")
NAME = "popLater is not defined"


def test_losing_every_late_script_breaks_on_pop_later() -> None:
    """The four scripts after the sixth are refused: the first error names popLater."""
    assert NAME in first_error(LATE)


def test_losing_cards_alone_breaks_on_pop_later() -> None:
    """The function popLater lives in cards.js, so refusing that file alone gives its error."""
    assert NAME in first_error(("cards.js",))


def test_losing_the_other_late_scripts_does_not_break_on_pop_later() -> None:
    """With cards.js served, refusing the other three never makes popLater the error."""
    assert NAME not in first_error(OTHERS)


def test_the_late_scripts_are_those_the_page_loads_after_the_sixth() -> None:
    """The files refused above are the page's last four script tags, in this order."""
    page = (Path(str(files("nemik.web"))) / "index.html").read_text()
    sources = [part.split('"')[0] for part in page.split('<script src="')[1:]]
    assert tuple(sources[SIXTH:]) == LATE
