# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W407: a card's compact OSLC resource and its small preview document."""

from nemik.preview import cite, compact, document_path, escape, preview_html

BASE = "https://pod.test/"


def test_a_card_is_cited_as_repo_and_symbol() -> None:
    """The fleet's own form, repo:W<n>."""
    assert cite("nemik", "W407") == "nemik:W407"


def test_the_compact_resource_has_the_oslc_core_keys() -> None:
    """Part 3: title, shortTitle, and a smallPreview with document and size hints."""
    got = compact(BASE, "nemik", "W407", "A preview")
    assert got["title"] == "nemik:W407: A preview"
    assert got["shortTitle"] == "nemik:W407"
    small = got["smallPreview"]
    assert small == {
        "document": BASE + "preview/nemik/W407.html",
        "hintWidth": "320px",
        "hintHeight": "72px",
    }


def test_the_document_path_sits_under_preview_by_repo() -> None:
    """One file per card, grouped by workstream."""
    assert document_path("a", "W1") == "preview/a/W1.html"


def test_the_preview_document_names_the_card_its_state_and_blockers() -> None:
    """A blocked card lists what it waits on; a ready one has no blocker line."""
    blocked = preview_html("a", "W1", "Title", "blocked", ["b:W2", "operator"])
    assert "<b>a:W1</b> Title" in blocked
    assert "state: blocked" in blocked
    assert "blocked on: b:W2, operator" in blocked
    assert "blocked on" not in preview_html("a", "W1", "Title", "ready", [])


def test_every_value_is_escaped_in_the_preview_document() -> None:
    """A title cannot inject markup into the page that embeds the preview."""
    html = preview_html("a", "W1", '<script>x()</script> & "y"', "ready", [])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html
    assert "&quot;y&quot;" in html
    assert escape("a&b") == "a&amp;b"
