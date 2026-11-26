# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2526: the vocabulary strings and the adapter's namespace objects name the same IRIs."""

from nemik import adapter, index, vocab

SHIPPED = {
    "OSLC_CM": "http://open-services.net/ns/cm#",
    "OSLC": "http://open-services.net/ns/core#",
    "NEMIK": "https://github.com/mikemol/nemik/ns#",
}
BASE = "urn:nemik:"


def test_every_iri_is_unchanged_byte_for_byte() -> None:
    """The bases the graph and the exports were built with are the bases now."""
    assert SHIPPED["OSLC_CM"] == vocab.OSLC_CM_BASE
    assert SHIPPED["OSLC"] == vocab.OSLC_BASE
    assert SHIPPED["NEMIK"] == vocab.NEMIK_BASE
    assert BASE == vocab.BASE


def test_the_adapters_namespaces_are_built_from_the_strings() -> None:
    """One source for each IRI: the adapter's terms equal a term made from the string."""
    assert str(adapter.OSLC_CM.state) == vocab.OSLC_CM_BASE + "state"
    assert str(adapter.OSLC.Compact) == vocab.OSLC_BASE + "Compact"
    assert str(adapter.NEMIK.enables) == vocab.NEMIK_BASE + "enables"
    assert adapter.BASE == vocab.BASE


def test_every_status_word_names_its_term() -> None:
    """The adapter's STATE maps each word to the NEMIK term the vocabulary names."""
    assert set(adapter.STATE) == set(vocab.STATE_NAMES)
    for status, name in vocab.STATE_NAMES.items():
        assert str(adapter.STATE[status]) == vocab.NEMIK_BASE + name


def test_the_index_builds_the_same_terms_it_used_to_import() -> None:
    """The terms index asks the graph for equal the adapter's, so a graph answers as before."""
    assert adapter.OSLC_CM.state == index.STATE
    assert adapter.NEMIK.enables == index.ENABLES
    assert adapter.NEMIK.waitsFor == index.WAITS_FOR
    assert adapter.NEMIK.Done == index.DONE
    assert adapter.NEMIK.Blocked == index.BLOCKED
