# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2526: nemik's RDF vocabulary as plain strings: the IRI bases and the status words.

A module that needs only these names (index, idle, the readers of the graph) used to import them
from nemik.adapter, whose own imports (rdflib's graph machinery, importlib.metadata,
mikemol.pathsforward, the warrant and retro readers) put every wall of those in the importer's
reach. These are strings and one import of the pure urnbase, so the Codon census compiles this
module and adds no failing row. A module that needs real rdflib terms builds them where it uses
them (Namespace(NEMIK_BASE), or URIRef(NEMIK_BASE + "Done")); nemik.adapter builds its namespace
objects from the same strings, so there is one source of every IRI (tests/test_vocab.py holds the
two to the same bytes).
"""

from nemik.urnbase import BASE as URN_BASE

BASE = URN_BASE
OSLC_CM_BASE = "http://open-services.net/ns/cm#"
OSLC_BASE = "http://open-services.net/ns/core#"
NEMIK_BASE = "https://github.com/mikemol/nemik/ns#"
# a status word as the local name of its NEMIK term; landed (nemik:W840, mtools:W1643) is
# committed with its deploy not yet witnessed: open, so closed stays false
STATE_NAMES = {
    "ready": "Ready",
    "working": "Working",
    "blocked": "Blocked",
    "landed": "LandedStatus",
    "done": "Done",
}
