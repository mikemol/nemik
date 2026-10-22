# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W859: a published history document says how old it is and is never guessed at."""

from nemik.histdocs import MODES, decode, encode, file_name, stale, valid, wrap

NOW = "2026-10-22T10:00:00Z"
CUTOFF = "2026-10-21T08:00:00Z"
BODY = '[{"cite": "alpha:W1"}]'
NOTHING = ("", "")


def test_a_stamp_is_exactly_the_fixed_form() -> None:
    """Digits, dashes, T, colons and Z in place; anything else is not a stamp."""
    assert valid(NOW)
    assert not valid("2026-10-22 10:00:00Z")
    assert not valid("2026-10-22T10:00:00")
    assert not valid("2026-1a-22T10:00:00Z")
    assert not valid("")


def test_a_document_round_trips_through_its_text() -> None:
    """The stamp is the first line and the body follows it untouched."""
    text = encode(NOW, BODY)
    assert text == f"{NOW}\n{BODY}"
    assert decode(text) == (NOW, BODY)


def test_a_text_with_no_stamp_reads_as_nothing() -> None:
    """A bad first line, or no newline, decodes to the empty pair; nothing unreadable is written."""
    assert decode(f"yesterday\n{BODY}") == NOTHING
    assert decode(NOW) == NOTHING
    assert not encode("yesterday", BODY)


def test_a_document_older_than_the_cutoff_is_stale() -> None:
    """Stamps sort as text, so the cutoff compares directly; an unreadable stamp is stale."""
    assert not stale(NOW, CUTOFF)
    assert stale("2026-10-20T10:00:00Z", CUTOFF)
    assert stale("yesterday", CUTOFF)


def test_only_the_named_modes_have_a_file() -> None:
    """A request path cannot name another file."""
    assert [file_name(mode) for mode in MODES] == [f"{mode}.json" for mode in MODES]
    assert not file_name("../hostroot")
    assert not file_name("oldest")


def test_the_wrapped_document_carries_its_age_and_the_body_as_published() -> None:
    """The body is not parsed: it appears verbatim under rows."""
    fresh = wrap("waits", NOW, BODY, CUTOFF)
    assert fresh == (
        '{"mode": "waits", "as_of": "2026-10-22T10:00:00Z", "stale": false, '
        f'"rows": {BODY}}}'
    )
    assert '"stale": true' in wrap("waits", "2026-10-20T10:00:00Z", BODY, CUTOFF)


def test_a_missing_document_or_unknown_mode_wraps_to_nothing() -> None:
    """The route answers not-found rather than a guess."""
    assert not wrap("waits", "", "", CUTOFF)
    assert not wrap("oldest", NOW, BODY, CUTOFF)
