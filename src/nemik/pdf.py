# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik-pdf: print one of the page's standard views to a PDF (nemik:W892, W890).

    python -m nemik.pdf VIEW --out FILE [--repo REPO] [--url URL]

The operator asked (2026-10-23) for an agent to render the graph to a file that can be read on a
phone. The page keeps no view in its URL, so this opens it in headless Chromium through playwright,
sets the view's controls (pdfviews), waits for the page's own redraw, and prints. It prints the
page of a running nemik-serve (the host's, on port 8765, unless --url names another); it starts no
server. It is a host tool: playwright and mikemol.webpage are development dependencies, not the
pod's.
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
    until(page, REDRAWN)


def render(url: str, view: str, repo: str, out: Path) -> None:
    """Print a view of the page at `url` to `out`.

    Args:
        url: A running nemik-serve.
        view: One of pdfviews.NAMES.
        repo: The repo for the repo view.
        out: The PDF to write.

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
            page.pdf(path=str(out), landscape=True, print_background=True)
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
