# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W254: translate each SPARQL constraint of the shapes once per survey, not per focus node.

pyshacl runs a SPARQL-based constraint by handing rdflib the same query text for every focus node
(the focus node travels as an initial binding), and rdflib parses and translates that text each
time: 1,290 parses, about 27 s of a 67 s profile of `nemik-rank --all`.

What is reused is the TRANSLATED query, the object rdflib's own `prepareQuery` returns and documents
as reusable across evaluations with different `initBindings`. The parse tree is not shared: rdflib's
translation rewrites it in place and its nodes cannot be deep-copied. `parseQuery` is therefore made
lazy (it returns the text), and `translateQuery` parses and translates it the first time that text,
base and namespaces are seen.

The patch is scoped: it lives for the `with` block and the originals are restored on exit, so
nothing outside a survey sees it.

The block holds a process-wide lock (reentrant, so a nested block is fine). Two threads in it at
once broke both halves (test_serve_model, 2026-10-13, under host load): the second entrant saved the
first one's patch as "the originals" and re-installed it for good on exit, and pyparsing, which
rdflib parses SPARQL with, is not thread-safe (its parse-action arity detection is shared state).
One survey at a time is what nemik-serve's Model asks for anyway.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, NamedTuple, cast

from rdflib.plugins.sparql import processor

_LOCK = threading.RLock()

if TYPE_CHECKING:
    from collections.abc import Callable


class _Text(NamedTuple):
    """A query whose parse is deferred until it is translated."""

    text: str


def _lazy(text: str) -> _Text:
    return _Text(text)


def _install() -> tuple[object, object]:
    # install the lazy parse and a cached translate in rdflib's processor, under the lock the
    # caller holds; give back the two originals for _restore
    module = cast("dict[str, object]", vars(processor))
    parse = cast("Callable[[str], object]", module["parseQuery"])
    translate = cast(
        "Callable[[object, object, object], object]", module["translateQuery"]
    )
    queries: dict[tuple[str, object, str], object] = {}

    def cached(tree: object, base: object = None, init_ns: object = None) -> object:
        if not isinstance(tree, _Text):
            return translate(tree, base, init_ns)
        namespaces: dict[str, object] = (
            cast("dict[str, object]", init_ns) if init_ns else {}
        )
        key = (tree.text, base, repr(sorted(namespaces.items(), key=str)))
        if key not in queries:
            queries[key] = translate(parse(tree.text), base, init_ns)
        return queries[key]

    module["parseQuery"], module["translateQuery"] = _lazy, cached
    return parse, translate


def _restore(parse: object, translate: object) -> None:
    # put the two originals _install gave back into rdflib's processor
    module = cast("dict[str, object]", vars(processor))
    module["parseQuery"], module["translateQuery"] = parse, translate


class CachedParse:
    """The block that reuses each distinct SPARQL query's translated form (nemik:W2182).

    nemik:W2182 (codon paydown): this was a contextlib.contextmanager generator, and contextlib is
    a Codon wall that shaclcache carried alone for three module-wall pairs. It is the same block
    written as a class with __enter__ and __exit__, which `with` calls the same way: enter takes the
    lock and installs the patch, exit restores the originals and releases the lock, also when the
    block raised (the exception is not swallowed).
    """

    def __init__(self) -> None:
        """Start with nothing saved: the originals are read on entry, under the lock."""
        self.parse: object = None
        self.translate: object = None

    def __enter__(self) -> None:
        """Take the lock, save the originals and install the lazy parse and cached translate.

        The originals are read under the lock: read before it, a second thread would save the first
        thread's patch as the originals. A nested block in the same thread saves and restores the
        outer patch, which still parses and translates correctly.
        """
        _LOCK.acquire()
        try:
            self.parse, self.translate = _install()
        except BaseException:
            _LOCK.release()
            raise

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Put the originals back and release the lock; an exception from the block goes on."""
        try:
            _restore(self.parse, self.translate)
        finally:
            _LOCK.release()


def cached_sparql_parse() -> CachedParse:
    """Reuse the translated form of each distinct SPARQL query for the duration of a `with` block.

    Returns:
        The block: a query text parses and translates once per base and namespace set inside it.

    """
    return CachedParse()
