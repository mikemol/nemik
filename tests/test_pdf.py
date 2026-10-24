# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W892: nemik-pdf sets a view's controls and prints a PDF; the views are pure steps."""

from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError

from nemik import pdfviews
from nemik.pdf import render

MIN_PDF_BYTES = 1000


def test_each_view_is_steps_on_known_controls() -> None:
    """Every view names a control by id, name or repo button, and the repo view needs a repo."""
    for view in pdfviews.NAMES:
        found = pdfviews.steps(view, "mtools")
        assert found
        assert all(action in {"check", "click", "select"} for action, _, _ in found)


def test_the_repo_view_picks_the_repo_and_two_hops() -> None:
    """One repo's button is clicked and the hop count is set to two."""
    assert pdfviews.steps(pdfviews.REPO, "nemik") == [
        ("click", '#repos button[data-repo="nemik"]', ""),
        ("select", "#depth", "2"),
    ]


def test_the_repo_view_without_a_repo_is_refused() -> None:
    """There is no whole-fleet repo view."""
    with pytest.raises(ValueError, match="needs a repo"):
        pdfviews.steps(pdfviews.REPO)


def test_an_unknown_view_is_refused_with_the_names() -> None:
    """The error lists the views that exist."""
    with pytest.raises(ValueError, match="treemap"):
        pdfviews.steps("poster")


def test_the_address_view_sets_no_control_and_joins_the_address() -> None:
    """The page picks from the address it opens at, so no steps; at() puts it in the URL."""
    assert pdfviews.steps(pdfviews.ADDRESS) == []
    assert pdfviews.ADDRESS not in pdfviews.NAMES
    assert pdfviews.at("http://h:8765/", "#/mtools/W5") == "http://h:8765/#/mtools/W5"
    assert pdfviews.at("http://h:8765/#/old", "#/new") == "http://h:8765/#/new"


def test_an_address_must_start_with_hash_slash() -> None:
    """A bare repo name or a path is refused, so a typo cannot print the wrong thing."""
    for bad in ("mtools", "/mtools", "#mtools", ""):
        with pytest.raises(ValueError, match="starts with #/"):
            pdfviews.at("http://h:8765/", bad)


def test_the_address_view_prints_a_pdf(tmp_path: Path) -> None:
    """Opened at a repo's address, the page prints to a PDF as a named view does."""
    out = tmp_path / "address.pdf"
    with webpage.served() as url:
        try:
            render(pdfviews.at(url, "#/mtools"), pdfviews.ADDRESS, "", out)
        except PlaywrightError as error:
            pytest.skip(f"chromium unavailable: {error}")
    assert out.read_bytes().startswith(b"%PDF")


@pytest.mark.parametrize("view", pdfviews.NAMES)
def test_a_view_prints_a_pdf(view: str, tmp_path: Path) -> None:
    """The fixture fleet, served and printed, gives a file that starts as a PDF."""
    out = tmp_path / f"{view}.pdf"
    with webpage.served() as url:
        try:
            render(url, view, "mtools", out)
        except PlaywrightError as error:
            pytest.skip(f"chromium unavailable: {error}")
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > MIN_PDF_BYTES
    assert b"MediaBox [0 0 1275.12 937.91998]" in data
    assert b"/Subtype /Image" not in data
