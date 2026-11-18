# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2284: which facts a Rego witness reads, from the witnesses the queue actually holds."""

from nemik.witnessreads import refs


def test_the_hand_written_git_ref_form_reads_a_field_no_observer_makes() -> None:
    """The form nine landed cards carried: its field is `resolves`, which git_ref never answers."""
    text = 'input.git_ref["nemik@6230c2a9a0551df15449140d1000500e720db733"].resolves == true'
    assert refs(text) == [
        ("git_ref", "nemik@6230c2a9a0551df15449140d1000500e720db733", "resolves")
    ]


def test_a_key_with_escaped_quotes_is_read_back_whole() -> None:
    """A PromQL key holds quotes of its own, escaped in the Rego text."""
    text = 'input.promql["up{job=\\"forgejo\\"}"].values[0] == 1'
    assert refs(text) == [("promql", 'up{job="forgejo"}', "values")]


def test_several_references_come_back_in_reading_order() -> None:
    """Two facts in one witness are both named, the second after the first."""
    text = (
        'input.alert["RegistryDown"].state == "inactive" and '
        'input.apply["host:home-mount"].applied'
    )
    assert refs(text) == [
        ("alert", "RegistryDown", "state"),
        ("apply", "host:home-mount", "applied"),
    ]


def test_a_reference_that_stops_at_the_bracket_has_no_field() -> None:
    """A fact read whole, such as a count over a pid fact, names an empty field."""
    assert refs('count(input.pid["localhost/1"]) > 0') == [("pid", "localhost/1", "")]


def test_text_without_a_keyed_fact_reads_nothing() -> None:
    """`input.now` is not a fact, an unterminated key never closes, and plain text names none."""
    assert refs("time.parse_rfc3339_ns(input.now) >= 1") == []
    assert refs('input.file["unterminated') == []
    assert refs("1 + 1 == 2") == []
    assert refs("") == []


def test_a_raw_backtick_key_is_read_as_written() -> None:
    """Rego's raw string holds quotes and backslashes as they are: no escapes inside it."""
    text = 'input.promql[`up{job="x"}`].values[0] == 1 and input.file[`a\\b`].exists'
    assert refs(text) == [
        ("promql", 'up{job="x"}', "values"),
        ("file", "a\\b", "exists"),
    ]


def test_an_unclosed_key_is_skipped_and_the_references_around_it_are_kept() -> None:
    """A key that never closes is no fact; the one before it is still read, and a raw one too."""
    assert refs('input.alert["A"].state and input.file["never') == [
        ("alert", "A", "state")
    ]
    assert refs("input.file[`never") == []
