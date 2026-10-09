"""nemik:W254: a SPARQL constraint is translated once per survey, with the same answers as before."""

from __future__ import annotations

from rdflib import Graph, Literal, Namespace, URIRef, Variable
from rdflib.plugins.sparql import processor

from nemik.shaclcache import cached_sparql_parse

EX = Namespace("urn:t:")
QUERY = "SELECT ?v WHERE { ?this <urn:t:p> ?v }"
V = Variable("v")


def _graph() -> Graph:
    g = Graph()
    g.add((EX.a, EX.p, Literal("first")))
    g.add((EX.b, EX.p, Literal("second")))
    return g


def _values(g: Graph, this: URIRef) -> list[str]:
    result = g.query(QUERY, initBindings={"this": this})
    return [str(row[V]) for row in result.bindings]


def test_one_translated_query_answers_correctly_for_different_bindings() -> None:
    g = _graph()
    with cached_sparql_parse():
        first = _values(g, EX.a)
        second = _values(g, EX.b)
        again = _values(g, EX.a)
    assert first == ["first"]
    assert second == ["second"]
    assert again == first


def test_the_text_is_translated_once_however_often_it_is_asked() -> None:
    g = _graph()
    translated: list[str] = []
    original = vars(processor)["translateQuery"]

    def spy(tree: object, base: object = None, init_ns: object = None) -> object:
        translated.append(type(tree).__name__)
        return original(tree, base, init_ns)

    vars(processor)["translateQuery"] = spy
    try:
        with cached_sparql_parse():
            for _ in range(5):
                _values(g, EX.a)
    finally:
        vars(processor)["translateQuery"] = original
    assert len(translated) == 1


def test_the_originals_are_back_after_the_block() -> None:
    before = vars(processor)["parseQuery"], vars(processor)["translateQuery"]
    with cached_sparql_parse():
        assert vars(processor)["parseQuery"] is not before[0]
    after = vars(processor)["parseQuery"], vars(processor)["translateQuery"]
    assert after == before


def test_a_query_outside_the_block_parses_as_always() -> None:
    assert _values(_graph(), EX.b) == ["second"]
