# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1179: the static server's content types are a fixed table, equal to what mimetypes said.

The server asked the host's mimetypes module for any suffix its own five-entry table lacked, a Codon
wall and an answer that also depends on the machine's mime.types. The table now names the other
suffixes a publish carries, and everything unlisted is served as octet-stream. The oracle is the OLD
lookup, rebuilt here with mimetypes, compared over every suffix src/nemik/serve.py publishes: the
page assets (.html .js .css), the wasm core (.wasm and its .sha256), the documents (.json .ttl)
and the two docs pages (.md).
"""

import mimetypes

import pytest

from nemik.staticserve import TYPES, UNKNOWN_TYPE

OLD_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript",
    ".json": "application/json",
    ".ttl": "text/turtle",
    ".css": "text/css",
}
PUBLISHED = [
    ".html",
    ".js",
    ".json",
    ".jsonld",
    ".ttl",
    ".css",
    ".wasm",
    ".md",
    ".sha256",
]
ADDED = [".jsonld", ".wasm", ".svg", ".ics", ".md", ".txt"]


def _old(suffix: str) -> str:
    # the type the server answered before the table replaced the fallback
    return OLD_TYPES.get(suffix) or (
        mimetypes.guess_type(f"x{suffix}")[0] or "application/octet-stream"
    )


def _new(suffix: str) -> str:
    return TYPES.get(suffix, UNKNOWN_TYPE)


@pytest.mark.parametrize("suffix", PUBLISHED)
def test_a_published_suffix_gets_the_type_the_old_lookup_gave(suffix: str) -> None:
    """Over every suffix a publish carries, the table answers as mimetypes did."""
    assert _new(suffix) == _old(suffix)


@pytest.mark.parametrize("suffix", ADDED)
def test_an_added_suffix_is_what_mimetypes_answered(suffix: str) -> None:
    """The suffixes added to the table keep the type the old fallback gave them."""
    assert TYPES[suffix] == mimetypes.guess_type(f"x{suffix}")[0]


def test_a_wasm_file_is_served_as_application_wasm() -> None:
    """A browser compiles a wasm stream only when it is served with this exact type."""
    assert _new(".wasm") == "application/wasm"


def test_the_five_old_entries_are_kept_verbatim() -> None:
    """The entries the table always had are unchanged."""
    assert {k: TYPES[k] for k in OLD_TYPES} == OLD_TYPES


def test_a_suffix_nobody_listed_is_served_as_octet_stream() -> None:
    """core.wasm.sha256 and any unlisted suffix fall to the unknown type."""
    assert ".sha256" not in TYPES
    assert _new(".sha256") == "application/octet-stream"
