# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W838: the waypoint states scheme gains landed, between working and done."""

from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "src" / "nemik" / "data" / "nemik.ttl"
TEXT = DATA.read_text(encoding="utf-8")
STATES = 5  # ready, working, blocked, landed, done


def _statement(subject: str) -> str:
    """Read one Turtle statement of the vocabulary: from its subject to the closing ' .'.

    Returns:
        The statement's text, empty when the subject has none.

    """
    at = TEXT.find(f"\n{subject} a ")
    if at < 0:
        return ""
    return TEXT[at : TEXT.index(" .\n", at)]


def test_the_scheme_has_five_states_and_landed_is_a_top_concept() -> None:
    """Five concepts in the one scheme: landed joins it, and no second scheme is made."""
    assert TEXT.count("skos:inScheme nemik:WaypointStates") == STATES
    assert "nemik:LandedStatus" in _statement("nemik:WaypointStates")
    assert 'skos:prefLabel "landed"' in _statement("nemik:LandedStatus")


def test_landed_is_close_to_cm_fixed_and_done_to_cm_verified() -> None:
    """A landed commit is CM's Fixed (not yet verified); done is its Verified."""
    assert "skos:closeMatch oslc_cm:Fixed" in _statement("nemik:LandedStatus")
    assert "skos:closeMatch oslc_cm:Verified" in _statement("nemik:Done")


def test_landed_says_what_it_is_and_what_witnesses_it() -> None:
    """A definition and the evidence that the deploy happened, as the lifecycle steps carry."""
    landed = _statement("nemik:LandedStatus")
    assert "skos:definition" in landed
    assert "nemik:witnessedBy" in landed


def test_the_deploys_flag_and_the_landing_stamp_are_declared_properties() -> None:
    """The two fields the queue writer adds to a card (mtools:W1643) have names here."""
    assert _statement("nemik:deploys")
    assert _statement("nemik:landedAt")
