# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W354: the catalog points each repo's provider at its published outbox."""

from rdflib import URIRef

from nemik.catalog import AS, catalog


def test_each_provider_links_its_outbox_relative_to_the_catalog() -> None:
    """The outbox IRI is relative, as the TRS links are, so it holds wherever the view is hosted."""
    g = catalog(["alpha", "beta"])
    provider = URIRef("catalog.ttl#alpha")
    assert list(g.objects(provider, AS.outbox)) == [URIRef("outbox/alpha.jsonld")]
    assert list(g.objects(URIRef("catalog.ttl#beta"), AS.outbox)) == [
        URIRef("outbox/beta.jsonld")
    ]
