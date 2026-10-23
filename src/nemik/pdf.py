# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik-pdf: print one of the page's standard views to a PDF (nemik:W892, W890).

    python -m nemik.pdf VIEW --out FILE [--repo REPO] [--url URL]

The operator asked (2026-10-23) for an agent to render the graph to a file that can be read on a
phone, and (W899) with no raster step between the model and the page. The page keeps no view in its
URL, so this opens it in headless Chromium through playwright, sets the view's controls (pdfviews),
waits for the page's own redraw, redraws the graph as SVG (web/svgexport.js, W900) over its canvas,
and prints: the PDF holds paths and text, no image of the canvas. It prints the page of a running
nemik-serve (the host's, on port 8765, unless --url names another); it starts no server. It is a
host tool: playwright and mikemol.webpage are development dependencies, not the pod's.
"""

import argparse
import os
import sys
from pathlib import Path

from mikemol.webpage.page import load, until
from playwright.sync_api import Page, ViewportSize, sync_playwright

from nemik import pdfviews

HOST_URL = "http://127.0.0.1:8765/"
# the page has drawn its graph
CY_READY = "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 1"
# two animation frames have passed, so a changed control has redrawn
REDRAWN = (
    "() => new Promise(done =>"
    " requestAnimationFrame(() => requestAnimationFrame(() => done(true))))"
)
VIEWPORT: ViewportSize = {"width": 1700, "height": 1250}
# the PDF's page is the viewport's own size, so the header, the graph and the panels all fit on it
PAGE_WIDTH = f"{VIEWPORT['width']}px"
PAGE_HEIGHT = f"{VIEWPORT['height']}px"
# the button that fits every repo on the screen; the page shows it when it is zoomed to one
FIT_ALL = "#fitall"
# the graph is a canvas, which prints as a picture; svgexport.js redraws it as vector (nemik:W900)
# and this puts that drawing over the canvas, which is hidden, so the PDF holds paths and text
SVG_EXPORT = Path(__file__).parent / "web" / "svgexport.js"
# The container keeps the size it has on screen, in pixels: in print layout a percentage height can
# collapse to nothing and the drawing vanishes from the page (the first vector PDF came out blank).
VECTORIZE = """() => {
  const host = document.getElementById('cy');
  const box = host.getBoundingClientRect();
  host.style.cssText += `;width:${box.width}px;height:${box.height}px;overflow:hidden`;
  host.insertAdjacentHTML('beforeend', graphSvg(cy));
  const svg = host.lastElementChild;
  svg.removeAttribute('width');
  svg.removeAttribute('height');
  svg.style.cssText = `position:absolute;left:0;top:0;width:${box.width}px;height:${box.height}px;`
    + 'z-index:5;background:#f7f7f5';
  host.querySelectorAll('canvas').forEach(c => { c.style.visibility = 'hidden'; });
}"""
# the drawing's area on the printed page, in square pixels: zero means it would print blank
DRAWN_AREA = (
    "() => { const r = document.getElementById('cy').lastElementChild.getBoundingClientRect();"
    " return r.width * r.height; }"
)


class _Options(argparse.Namespace):
    """The command line, typed."""

    view: str
    out: Path
    repo: str
    url: str


def apply(page: Page, view: str, repo: str) -> None:
    """Set a view's controls on a loaded page, then wait for its redraw.

    Args:
        page: A page on which the graph has drawn.
        view: One of pdfviews.NAMES.
        repo: The repo for the repo view.

    """
    for action, selector, value in pdfviews.steps(view, repo):
        if action == "check":
            page.check(selector)
        elif action == "click":
            page.click(selector)
        else:
            page.select_option(selector, value)
    if page.locator(FIT_ALL).count():
        page.click(FIT_ALL)
    until(page, REDRAWN)


def render(url: str, view: str, repo: str, out: Path) -> None:
    """Print a view of the page at `url` to `out`.

    Args:
        url: A running nemik-serve.
        view: One of pdfviews.NAMES.
        repo: The repo for the repo view.
        out: The PDF to write.

    Raises:
        RuntimeError: when the graph's drawing would have no area on the printed page.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=str(Path(exe).absolute()) if exe else None
        )
        try:
            page = browser.new_page(viewport=VIEWPORT)
            load(page, url, CY_READY)
            apply(page, view, repo)
            page.add_script_tag(path=str(SVG_EXPORT))
            page.evaluate(VECTORIZE)
            page.emulate_media(media="print")
            area: object = page.evaluate(DRAWN_AREA)
            if not area:
                msg = "the graph's drawing has no area in print layout; the PDF would be blank"
                raise RuntimeError(msg)
            page.pdf(
                path=str(out),
                width=PAGE_WIDTH,
                height=PAGE_HEIGHT,
                print_background=True,
            )
        finally:
            browser.close()


def main(argv: list[str] | None = None) -> int:
    """Render the named view.

    Returns:
        0 when the PDF was written; 2 for an unknown view or a repo view with no repo.

    """
    parser = argparse.ArgumentParser(prog="python -m nemik.pdf", description=__doc__)
    parser.add_argument("view", help=f"one of {', '.join(pdfviews.NAMES)}")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo", default="", help="for the repo view")
    parser.add_argument("--url", default=HOST_URL, help="a running nemik-serve")
    options = parser.parse_args(argv, namespace=_Options())
    try:
        pdfviews.steps(options.view, options.repo)
    except ValueError as error:
        sys.stderr.write(f"nemik-pdf: {error}\n")
        return 2
    render(options.url, options.view, options.repo, options.out)
    sys.stdout.write(f"{options.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
