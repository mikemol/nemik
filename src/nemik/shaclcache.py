"""nemik:W254: translate each SPARQL constraint of the shapes once per survey, not once per focus node.

pyshacl runs a SPARQL-based constraint by handing rdflib the same query text for every focus node
(the focus node travels as an initial binding), and rdflib parses and translates that text each time:
1,290 parses, about 27 s of a 67 s profile of `nemik-rank --all`.

What is reused is the TRANSLATED query, the object rdflib's own `prepareQuery` returns and documents
as reusable across evaluations with different `initBindings`. The parse tree is not shared: rdflib's
translation rewrites it in place and its nodes cannot be deep-copied. `parseQuery` is therefore made
lazy (it returns the text), and `translateQuery` parses and translates it the first time that text,
base and namespaces are seen.

The patch is scoped: it lives for the `with` block and the originals are restored on exit, so nothing
outside a survey sees it.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from rdflib.plugins.sparql import processor

if TYPE_CHECKING:
    from collections.abc import Iterator


class _Text:
    """A query whose parse is deferred until it is translated."""

    def __init__(self, text: str) -> None:
        self.text = text


@contextmanager
def cached_sparql_parse() -> Iterator[None]:
    """Reuse the translated form of each distinct SPARQL query for the duration of the block.

    Yields:
        nothing; a query text parses and translates once per base and namespace set.

    """
    module = vars(processor)
    parse, translate = module["parseQuery"], module["translateQuery"]
    queries: dict[tuple[str, Any, str], Any] = {}

    def lazy(text: str) -> _Text:
        return _Text(text)

    def cached(tree: Any, base: Any = None, init_ns: Any = None) -> Any:
        if not isinstance(tree, _Text):
            return translate(tree, base, init_ns)
        key = (tree.text, base, repr(sorted((init_ns or {}).items(), key=str)))
        if key not in queries:
            queries[key] = translate(parse(tree.text), base, init_ns)
        return queries[key]

    module["parseQuery"], module["translateQuery"] = lazy, cached
    try:
        yield
    finally:
        module["parseQuery"], module["translateQuery"] = parse, translate
