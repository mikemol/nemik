# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik-pdf: print one of the page's standard views to a PDF (nemik:W892, W890, W904).

    python -m nemik.pdf VIEW --out FILE [--repo REPO] [--url URL]

The operator asked (2026-10-23) for an agent to render the graph to a file that can be read on a
phone, and (W899) with no raster step between the model and the page. The page keeps no view in its
URL, so this opens it in headless Chromium through playwright, sets the view's controls (pdfviews),
waits for the page's own redraw, takes the graph as SVG from the page (web/svgexport.js, W900) and
hands that drawing to rsvg-convert: the PDF holds paths and text, no image of the canvas, and no
panels (operator 2026-10-28, W904: Chromium's own print flattens every dashed edge into segments, a
24.7 MB file against 0.44 MB from rsvg-convert, which keeps the dashes native). It reads the page of
a running nemik-serve (the host's, on port 8765, unless --url names another); it starts no server.
It is a host tool: playwright, mikemol.webpage and librsvg's rsvg-convert are development
dependencies, not the pod's.
"""

import os
import sys
import tempfile
from pathlib import Path

from mikemol.webpage.page import PageBrokenError, load, until
from playwright.sync_api import (
    Browser,
    Page,
    Request,
    Response,
    ViewportSize,
    sync_playwright,
)

from nemik import pdfviews
from nemik.flags import command_line, parse_flags


class Lookup:
    """The answer of a PATH search: what was found and where it looked (nemik:W1871)."""

    found: bool
    executable: str
    searched: list[str]

    def __init__(self, executable: str, searched: list[str]) -> None:
        """Hold the file found (empty when none was) and the directories searched."""
        self.executable = executable
        self.searched = searched
        self.found = bool(executable)


def search_path(name: str) -> Lookup:
    """Search PATH for an executable file, without shutil (nemik:W1871).

    It differs from shutil.which on purpose: an empty PATH entry is skipped (shutil reads it as
    the current directory, which would run a same-named file from wherever the tool is started),
    and an unset PATH searches nothing (shutil falls back to os.defpath).

    Returns:
        The first PATH entry's executable file called name, and the directories it searched, in
        order; `found` is False when no directory held one.

    """
    directories = [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    for directory in directories:
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return Lookup(str(candidate), directories)
    return Lookup("", directories)


HOST_URL = "http://127.0.0.1:8765/"
# nemik:W846: a response at or past this status is recorded as a failed request
HTTP_ERROR = 400
# nemik:W846: Chromium aborts every request in flight when the host's network configuration
# changes, whatever the server did; a load that lost only to that is tried again
NETWORK_CHANGED = "net::ERR_NETWORK_CHANGED"
LOAD_TRIES = 3
# the page has drawn its graph
CY_READY = "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 1"
# two animation frames have passed, so a changed control has redrawn
REDRAWN = (
    "() => new Promise(done =>"
    " requestAnimationFrame(() => requestAnimationFrame(() => done(true))))"
)
VIEWPORT: ViewportSize = {"width": 1700, "height": 1250}
# the button that fits every repo on the screen; the page shows it when it is zoomed to one
FIT_ALL = "#fitall"
# the graph is a canvas; svgexport.js redraws it as vector (nemik:W900) and its graphSvg(cy) is what
# rsvg-convert turns into the PDF
SVG_EXPORT = Path(__file__).parent / "web" / "svgexport.js"
# the page's own background, which the SVG does not draw (W904)
BACKGROUND = "#f7f7f5"
RSVG = "rsvg-convert"
GRAPH_SVG = "() => graphSvg(cy)"
VALUED = ["--out", "--repo", "--url", "--address"]
USAGE = (
    "usage: python -m nemik.pdf VIEW --out FILE [--repo REPO] [--url URL] [--address A]\n"
    "  VIEW           one of the views in nemik.pdfviews, or the address view\n"
    "  --out FILE     where the PDF goes (required)\n"
    "  --repo REPO    for the repo view\n"
    "  --url URL      a running nemik-serve\n"
    "  --address A    for the address view: #/<repo>[/W<n>], what the page opens at (nemik:W955)"
)
BAD_USAGE = 2  # argparse's exit status for a command line it could not read


class Command:
    """The parsed command line (nemik:W1869: read with nemik.flags, not argparse)."""

    view: str
    out: Path
    repo: str
    url: str
    address: str

    def __init__(self, view: str, out: Path, repo: str, url: str, address: str) -> None:
        """Hold the five options."""
        self.view = view
        self.out = out
        self.repo = repo
        self.url = url
        self.address = address


def read_options(argv: list[str] | None) -> Command:
    """Read nemik-pdf's command line, printing usage or errors and exiting like argparse.

    Args:
        argv: The command line; None reads the process's own.

    Returns:
        The options, each defaulted as the argparse form defaulted it.

    Raises:
        SystemExit: 0 after --help, 2 for an unrecognized argument, a flag with no value, a
            missing view or a missing --out.

    """
    words = command_line() if argv is None else argv
    flags = parse_flags(words, VALUED, ["--help"])
    if flags.has("--help") or "-h" in flags.rest:
        sys.stdout.write(USAGE + "\n")
        raise SystemExit(0)
    errors = list(flags.errors)
    errors.extend(f"unrecognized argument: {w}" for w in flags.rest[1:])
    if not flags.rest:
        errors.append("the following arguments are required: view")
    if not flags.every("--out"):
        errors.append("the following arguments are required: --out")
    if errors:
        sys.stderr.write(USAGE + "\n")
        sys.stderr.write("nemik.pdf: error: " + "; ".join(errors) + "\n")
        raise SystemExit(BAD_USAGE)
    return Command(
        flags.rest[0],
        Path(flags.first("--out", "")),
        flags.first("--repo", ""),
        flags.first("--url", HOST_URL),
        flags.first("--address", ""),
    )


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


class NetworkChangedError(PageBrokenError):
    """The page broke and every request it made died of a network change (nemik:W846)."""


def lost_to_a_network_change(refused: list[str]) -> bool:
    """Say whether the load failed only because the host's network configuration changed.

    Args:
        refused: The requests the page listed as failed or refused.

    Returns:
        True when there are some and every one of them died of net::ERR_NETWORK_CHANGED.

    """
    return bool(refused) and all(NETWORK_CHANGED in line for line in refused)


def load_naming_failures(page: Page, url: str) -> None:
    """Open `url` and wait for the graph, naming the requests that failed if the page breaks.

    A script that did not load under load leaves the page's first error as a missing name
    (`popLater is not defined`); the list of failed requests says which file it was (nemik:W846).

    Args:
        page: A new page.
        url: A running nemik-serve.

    Raises:
        NetworkChangedError: the page broke and every failed request died of a network
            change.
        PageBrokenError: the page broke while loading; the message lists the requests that
            failed or got an error status.

    """
    refused: list[str] = []

    def note_failed(request: Request) -> None:
        refused.append(f"failed {request.url} ({request.failure})")

    def note_status(response: Response) -> None:
        if response.status >= HTTP_ERROR:
            refused.append(f"{response.status} {response.url}")

    page.on("requestfailed", note_failed)
    page.on("response", note_status)
    try:
        load(page, url, CY_READY)
    except PageBrokenError as e:
        message = f"{e}; requests refused or failed: {refused}"
        if lost_to_a_network_change(refused):
            raise NetworkChangedError(message) from e
        raise PageBrokenError(message) from e


def loaded_page(browser: Browser, url: str) -> Page:
    """Open `url` in a new page, again on a fresh page when the network changed under the load.

    Args:
        browser: A launched browser.
        url: A running nemik-serve.

    Returns:
        The first page whose graph drew.

    Raises:
        NetworkChangedError: every try lost all its requests to a network change.

    """
    tries = 0
    while True:
        tries += 1
        page = browser.new_page(viewport=VIEWPORT)
        try:
            load_naming_failures(page, url)
        except NetworkChangedError:
            page.close()
            if tries >= LOAD_TRIES:
                raise
        else:
            return page


def svg_to_pdf(svg: str, out: Path) -> None:
    """Turn the graph's SVG into a PDF with rsvg-convert (nemik:W904).

    Args:
        svg: The drawing, as graphSvg(cy) returns it.
        out: The PDF to write.

    Raises:
        RuntimeError: when rsvg-convert is not installed, or it fails; the message carries its
            own error text.

    """
    lookup = search_path(RSVG)
    if not lookup.found:
        missing = (
            f"{RSVG} is not on the PATH (searched {', '.join(lookup.searched) or 'nothing'}); "
            "install librsvg to print the graph to a PDF"
        )
        raise RuntimeError(missing)
    exe = lookup.executable
    with tempfile.TemporaryDirectory() as work:
        source = Path(work) / "graph.svg"
        source.write_text(svg, encoding="utf-8")
        command = [
            exe,
            "--format=pdf",
            f"--background-color={BACKGROUND}",
            f"--output={out}",
            str(source),
        ]
        errors = Path(work) / "stderr.txt"
        # stderr goes to a file, so a failure can say why without a pipe to drain
        redirect = [
            (os.POSIX_SPAWN_OPEN, 2, str(errors), os.O_WRONLY | os.O_CREAT, 0o600)
        ]
        pid = os.posix_spawn(exe, command, os.environ, file_actions=redirect)
        status = os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1])
        said = errors.read_text(encoding="utf-8", errors="replace").strip()
    if status != 0:
        failed = f"{RSVG} failed with status {status}: {said}"
        raise RuntimeError(failed)


def render(url: str, view: str, repo: str, out: Path) -> None:
    """Print a view of the page at `url` to `out`.

    Args:
        url: A running nemik-serve.
        view: One of pdfviews.NAMES.
        repo: The repo for the repo view.
        out: The PDF to write.

    Raises:
        RuntimeError: when the page gives no drawing, or rsvg-convert fails.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=str(Path(exe).absolute()) if exe else None
        )
        try:
            page = loaded_page(browser, url)
            apply(page, view, repo)
            page.add_script_tag(path=str(SVG_EXPORT))
            drawing: object = page.evaluate(GRAPH_SVG)
        finally:
            browser.close()
    if not isinstance(drawing, str) or not drawing:
        msg = "the page gave no SVG drawing of its graph; the PDF would be blank"
        raise RuntimeError(msg)
    svg_to_pdf(drawing, out)


def main(argv: list[str] | None = None) -> int:
    """Render the named view.

    Returns:
        0 when the PDF was written; 2 for an unknown view or a repo view with no repo.

    """
    options = read_options(argv)
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
