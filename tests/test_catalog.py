# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W451: the published OSLC catalog lists every repo, and its TRS links resolve to published files."""

import json
from pathlib import Path

from rdflib import RDF, Graph

from nemik.catalog import OSLC
from nemik.serve import build_static
from nemik.trs import TRS

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_the_catalog_resolves_to_every_repos_tracked_resource_set(
    tmp_path: Path,
) -> None:
    """The catalog names each repo's tracked resource set."""
    withheld = tmp_path / "withheld.json"
    withheld.write_text(json.dumps({"version": 1, "as_of": "x", "items": []}))
    out = tmp_path / "out"
    build_static(FLEET, out, withheld)
    cat = out / "catalog.ttl"
    # parsed as a client would: relative links resolve against the catalog's own location
    g = Graph().parse(cat, format="turtle", publicID=cat.as_uri())
    roots = list(g.subjects(RDF.type, OSLC.ServiceProviderCatalog))
    assert len(roots) == 1
    providers = list(g.objects(roots[0], OSLC.serviceProvider))
    repos = sorted(p.name for p in (out / "trs").iterdir())
    assert len(providers) == len(repos) > 0
    for provider in providers:
        tracked = g.value(provider, TRS.trackedResourceSet)
        assert tracked is not None
        for link in (TRS.base, TRS.changeLog):
            target = g.value(tracked, link)
            assert target is not None
            path = Path(str(target).removeprefix("file://"))
            assert path.exists(), (provider, link, target)
