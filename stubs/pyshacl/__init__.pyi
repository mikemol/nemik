"""nemik:W1597: the part of pyshacl the validator and its tests use, typed (the library answers Any)."""

from rdflib import Graph

def validate(
    data_graph: Graph,
    *,
    shacl_graph: Graph | None = None,
    meta_shacl: bool = False,
) -> tuple[bool, Graph, str]: ...
