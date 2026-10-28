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

from mikemol.webpage.page import PageBrokenError, load, until
from playwright.sync_api import Page, Request, Response, ViewportSize, sync_playwright

from nemik import pdfviews

HOST_URL = "http://127.0.0.1:8765/"
# nemik:W846: a response at or past this status is recorded as a failed request
HTTP_ERROR = 400
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
    address: str


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


def load_naming_failures(page: Page, url: str) -> None:
    """Open `url` and wait for the graph, naming the requests that failed if the page breaks.

    A script that did not load under load leaves the page's first error as a missing name
    (`popLater is not defined`); the list of failed requests says which file it was (nemik:W846).

    Args:
        page: A new page.
        url: A running nemik-serve.

    Raises:
        PageBrokenError: the page broke while loading; the message lists the requests that
            failed or got an error status.

    """
    refused: list[str] = []

    def note_failed(request: Request) -> None:
        refused.append(f"failed {request.url}")

    def note_status(response: Response) -> None:
        if response.status >= HTTP_ERROR:
            refused.append(f"{response.status} {response.url}")

    page.on("requestfailed", note_failed)
    page.on("response", note_status)
    try:
        load(page, url, CY_READY)
    except PageBrokenError as e:
        message = f"{e}; requests refused or failed: {refused}"
        raise PageBrokenError(message) from e


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
            load_naming_failures(page, url)
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
    parser.add_argument(
        "view", help=f"one of {', '.join(pdfviews.NAMES)}, or {pdfviews.ADDRESS}"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo", default="", help="for the repo view")
    parser.add_argument("--url", default=HOST_URL, help="a running nemik-serve")
    parser.add_argument(
        "--address",
        default="",
        help="for the address view: #/<repo>[/W<n>], what the page opens at (nemik:W955)",
    )
    options = parser.parse_args(argv, namespace=_Options())
    try:
        pdfviews.steps(options.view, options.repo)
        opened = (
            pdfviews.at(options.url, options.address)
            if options.view == pdfviews.ADDRESS
            else options.url
        )
    except ValueError as error:
        sys.stderr.write(f"nemik-pdf: {error}\n")
        return 2
    render(opened, options.view, options.repo, options.out)
    sys.stdout.write(f"{options.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
