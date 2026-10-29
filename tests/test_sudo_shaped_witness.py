# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1262: the rule fires on the text the host relayed (luthen-observability:W1752, R96)."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import NEMIK, OSLC_CM
from nemik.blocks import sudo_shaped
from nemik.check import shapes
from nemik.shaclinc import findings

# luthen-observability commit 85603ff1 (2026-10-29 01:05:58 -0400), .claude/paths-forward.json line
# 37534, the blocked_on of W1752 before the md0 directories became a host row: read with git grep.
RELAYED = "operator: act run sudo install -d -o mikemol -g mikemol -m 0755 /srv/backup/mikemol"


def test_the_python_rule_flags_the_relayed_text() -> None:
    """The ask-row rule of W1264 flags the text that was relayed for about three hours."""
    assert sudo_shaped(RELAYED)


def test_the_warning_shape_flags_the_relayed_text() -> None:
    """The Warning shape of W1265 reports it for a blocked card with that blocked_on."""
    g = Graph()
    card = URIRef("urn:test:card/w1752")
    g.add((card, RDF.type, OSLC_CM.ChangeRequest))
    g.add((card, OSLC_CM.state, NEMIK.Blocked))
    g.add((card, NEMIK.blockedOn, Literal(RELAYED)))
    messages = [m for _, _, m in findings("w1752-relayed", g, shapes())]
    assert any("names a root-shaped command" in m for m in messages)
