# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W806: the page's files have a line ceiling each, and the ceilings only fall.

index.html was one 2,000-line file (operator 2026-10-20: "way, way, way too large"); W799 split
it by concern. This keeps it split: a file may not grow past its ceiling, and a file that shrank
must say so by lowering its ceiling here, so the number recorded is the number there is. A new
text page file needs a ceiling of its own before it can be served.
"""

from importlib.resources import files
from pathlib import Path

from nemik.serve import PAGE_FILES

WEB = Path(str(files("nemik.web")))
# the text files of the page and the lines each holds today; lower a number when its file shrinks
CEILINGS = {
    "index.html": 282,
    "graph.js": 607,
    "cards.js": 200,
    "panels.js": 312,
    "queue.js": 32,
    "viewstate.js": 23,
    "render.js": 382,
    "style.css": 80,
    "wasm.js": 220,
}
BINARY = {"core.wasm"}


def _lines(name: str) -> int:
    """Count a page file's lines.

    Returns:
        The number of lines in the file.

    """
    return len((WEB / name).read_text(encoding="utf-8").splitlines())


def test_no_page_file_is_past_its_ceiling() -> None:
    """A file that grew past its ceiling is split or trimmed, not given a higher number."""
    over = {n: (_lines(n), c) for n, c in CEILINGS.items() if _lines(n) > c}
    assert over == {}, f"past the ceiling (lines, ceiling): {over}"


def test_a_ceiling_that_is_not_met_is_lowered() -> None:
    """The ceiling is the size the file has: a shrunk file lowers its number, so it only falls."""
    slack = {n: (_lines(n), c) for n, c in CEILINGS.items() if _lines(n) < c}
    assert slack == {}, f"lower the ceiling to the lines (lines, ceiling): {slack}"


def test_every_text_page_file_has_a_ceiling() -> None:
    """index.html and each served text file is budgeted; a new one must declare its number."""
    served = {name for name in PAGE_FILES if name not in BINARY}
    assert served | {"index.html"} == set(CEILINGS)
