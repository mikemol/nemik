# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W943: a filed ask is also worded as an ActivityStreams Offer to its owner."""

import json

from nemik.ask import offer, quoted

CLAIM = 'a "quoted" claim\nover two lines, with a \\ backslash and a {brace}'


def test_a_text_is_quoted_as_json_would_quote_it() -> None:
    """The hand quoting round-trips through a real JSON parser."""
    back: object = json.loads(quoted(CLAIM))
    plain: object = json.loads(quoted("plain"))
    assert back == CLAIM
    assert plain == "plain"


def test_an_ask_is_an_offer_of_the_filers_card_to_the_owner() -> None:
    """The Offer parses and names the filer as actor, its card as object and the owner as target."""
    parsed: object = json.loads(offer("ask-x", "life", "mtools", CLAIM, "W7"))
    assert parsed == {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": "urn:nemik:ask:ask-x",
        "type": "Offer",
        "actor": "urn:nemik:life",
        "object": {
            "type": "Ticket",
            "id": "urn:nemik:life/W7",
            "summary": CLAIM,
        },
        "target": "urn:nemik:mtools",
    }
