# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W451: an OSLC service-provider catalog, the root an OSLC client discovers nemik from.

W373's study of Jazz found a missing service-provider catalog named as an integration failure
(a Polarion integrator hit it). This is nemik's: one oslc:ServiceProviderCatalog listing a
ServiceProvider per repo, each serving the Change Management domain and its
trs:TrackedResourceSet (W448/W449), whose base and change log are the Turtle files the static
build publishes.

Links are relative IRIs (`trs/<repo>/base.ttl`), resolved against the catalog's own URL as RDF
readers do, so the catalog is correct wherever the static view is hosted.
"""

from __future__ import annotations

from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS

from nemik.trs import TRS

OSLC = Namespace("http://open-services.net/ns/core#")
CM_DOMAIN = URIRef("http://open-services.net/ns/cm#")
AS = Namespace("https://www.w3.org/ns/activitystreams#")


def catalog(repos: list[str]) -> Graph:
    """Build the catalog graph for `repos`, every link relative to catalog.ttl.

    Returns:
        The graph: one ServiceProviderCatalog and, per repo, its provider, service and TRS set.

    """
    g = Graph()
    g.bind("oslc", OSLC)
    g.bind("trs", TRS)
    g.bind("dcterms", DCTERMS)
    root = URIRef("catalog.ttl")
    g.add((root, RDF.type, OSLC.ServiceProviderCatalog))
    g.add((root, DCTERMS.title, Literal("nemik: the fleet's workstreams")))
    g.add((root, OSLC.domain, CM_DOMAIN))
    for repo in sorted(repos):
        provider = URIRef(f"catalog.ttl#{repo}")
        service = URIRef(f"catalog.ttl#{repo}-cm")
        tracked = URIRef(f"catalog.ttl#{repo}-trs")
        g.add((root, OSLC.serviceProvider, provider))
        g.add((provider, RDF.type, OSLC.ServiceProvider))
        g.add((provider, DCTERMS.title, Literal(repo)))
        g.add((provider, OSLC.service, service))
        g.add((service, RDF.type, OSLC.Service))
        g.add((service, OSLC.domain, CM_DOMAIN))
        g.add((provider, TRS.trackedResourceSet, tracked))
        g.add((tracked, RDF.type, TRS.TrackedResourceSet))
        g.add((tracked, TRS.base, URIRef(f"trs/{repo}/base.ttl")))
        g.add((tracked, TRS.changeLog, URIRef(f"trs/{repo}/changelog.ttl")))
        # nemik:W354: the repo's read-only ForgeFed outbox, published beside its TRS feed
        g.add((provider, AS.outbox, URIRef(f"outbox/{repo}.jsonld")))
    return g
