# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W626: how far from its focus node a shape reads, so the incremental cache re-judges enough.

The SHACL cache (nemik.shaclinc) re-judges the neighbourhood of what changed. A shape that reads
further than that neighbourhood returns a stale verdict silently, so the radius is derived from the
shapes, not written down: the longest chain of graph patterns any sh:sparql query walks from $this,
counted in variable hops. A property shape names one predicate, so it reads one hop. A query whose
depth cannot be bounded (a property path, unbalanced braces) has no radius, and the caller falls
back to a full run.

The reading is of the query text, in strings only: the terms of each triple pattern are found, a
pattern joins its subject and its objects, and the distance from $this is counted over variables.
The caller hands over the constraints' texts, so nothing here depends on rdflib.
"""

import re

FLOOR = 1  # a property shape reads the value it names: one hop
UNBOUNDED = -1  # no radius: a query reads any distance, so the caller does a full run
TERM = re.compile(r'<[^>]*>[+*?]?|"[^"]*"|[?$]\w+|[\w:.-]+[+*?]?|[;,{}()|/^]')
FILTER = re.compile(r"FILTER\s*\(")
KEYWORDS = {"FILTER", "NOT", "EXISTS", "OPTIONAL", "UNION", "MINUS"}
ENDS = {".", "{", "}"}


def _strip_filters(text: str) -> str:
    """Drop every FILTER( ... ) expression, balanced; its comparisons read no pattern.

    Args:
        text: The query text.

    Returns:
        The text without them. FILTER NOT EXISTS { ... } keeps its braces: those are patterns.

    """
    out = text
    while True:
        found = FILTER.search(out)
        if found is None:
            return out
        level = 1
        end = found.end()
        while end < len(out) and level:
            level += {"(": 1, ")": -1}.get(out[end], 0)
            end += 1
        out = out[: found.start()] + " " + out[end:]


def _statements(body: str) -> list[list[str]]:
    """Split a query body into statements of terms.

    Args:
        body: The text after WHERE, filters stripped.

    Returns:
        The statements.

    Raises:
        ValueError: For a property path (| / ^ or a trailing + * ?), which has no bound.

    """
    out: list[list[str]] = []
    current: list[str] = []
    pieces: list[str] = TERM.findall(body)
    for piece in pieces:
        if piece in ENDS or piece in KEYWORDS:
            out.append(current)
            current = []
        elif piece in "|/^" or (piece[-1] in "+*?" and piece[0] not in "?$"):
            raise ValueError(piece)
        else:
            current.append(piece)
    out.append(current)
    return [s for s in out if len(s) > 1]


def _name(term: str) -> str:
    """Give a variable one spelling, so $this and ?this are the same node.

    Args:
        term: A term of the query.

    Returns:
        ?name for a variable, the term otherwise.

    """
    return "?" + term[1:] if term[0] in "?$" else term


def _pairs(statement: list[str]) -> list[tuple[str, str]]:
    """Read a statement's subject-object pairs: `s p o , o ; p o`.

    Args:
        statement: The terms of one statement.

    Returns:
        (subject, object) for each object, predicates left out.

    """
    segments: list[list[str]] = [[]]
    for term in statement:
        if term == ";":
            segments.append([])
        else:
            segments[-1].append(term)
    subject = _name(segments[0][0])
    rest = [segments[0][1:], *segments[1:]]
    return [
        (subject, _name(obj)) for segment in rest for obj in segment[1:] if obj != ","
    ]


def _reach(pairs: list[tuple[str, str]]) -> int:
    """Count the variable hops from $this to the furthest variable.

    Args:
        pairs: The subject-object pairs of a query's triple patterns.

    Returns:
        The longest shortest-path distance, over variables only, from ?this.

    """
    adjacent: dict[str, set[str]] = {}
    for subject, obj in pairs:
        if subject[0] == "?" and obj[0] == "?":
            adjacent.setdefault(subject, set()).add(obj)
            adjacent.setdefault(obj, set()).add(subject)
    seen: dict[str, int] = {"?this": 0}
    queue: list[str] = ["?this"]
    while queue:
        here = queue.pop(0)
        for there in adjacent.get(here, ()):
            if there not in seen:
                seen[there] = seen[here] + 1
                queue.append(there)
    return max(seen.values())


def query_depth(text: str) -> int:
    """Measure one constraint's reach.

    Args:
        text: The constraint's query text.

    Returns:
        Its variable hops from $this, or UNBOUNDED when unbounded.

    """
    where = text.upper().find("WHERE")
    body = _strip_filters(text[where + len("WHERE") :] if where >= 0 else text)
    if body.count("{") != body.count("}"):
        return UNBOUNDED
    try:
        found = _statements(body)
    except ValueError:
        return UNBOUNDED
    return _reach([pair for statement in found for pair in _pairs(statement)])


def depth(texts: list[str]) -> int:
    """Derive the radius the constraints need.

    Args:
        texts: The sh:sparql constraints' query texts.

    Returns:
        The deepest read of any of them (at least FLOOR), or UNBOUNDED when a query's depth
        cannot be bounded.

    """
    deepest = FLOOR
    for text in texts:
        reach = query_depth(text)
        if reach == UNBOUNDED:
            return UNBOUNDED
        deepest = max(deepest, reach)
    return deepest


_SEEN: dict[str, int] = {}


def radius(texts: list[str]) -> int:
    """Derive the radius once per distinct set of constraints.

    Args:
        texts: The sh:sparql constraints' query texts.

    Returns:
        depth(texts), remembered by the texts themselves so a survey does not parse them again.

    """
    key = "\n".join(sorted(texts))
    if key not in _SEEN:
        _SEEN[key] = depth(texts)
    return _SEEN[key]
