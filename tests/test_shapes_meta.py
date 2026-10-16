# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W529: shapes.ttl is itself valid SHACL, checked against the SHACL-SHACL meta shapes."""

import pytest
from pyshacl import validate
from rdflib import Graph

from nemik.check import shapes

BAD = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <urn:ex:> .
ex:S a sh:NodeShape ; sh:property [ sh:path ex:p ; sh:minCount "many" ] .
"""


def test_every_shape_in_shapes_ttl_is_well_formed_shacl() -> None:
    """The shapes graph validates against SHACL-SHACL; a malformed shape would raise."""
    validate(Graph(), shacl_graph=shapes(), meta_shacl=True)


def test_a_malformed_shape_is_refused_by_the_same_check() -> None:
    """The check is armed: a property shape with a non-integer sh:minCount is rejected."""
    bad = Graph()
    bad.parse(data=BAD, format="turtle")
    with pytest.raises(Exception, match="Shapes"):
        validate(Graph(), shacl_graph=bad, meta_shacl=True)
