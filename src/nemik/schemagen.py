# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: a JSON Schema per published file, and the OpenAPI document, built on the arena tree.

The same documents `apischema` used to build as nested dicts, written here as nodes of a `Tree`
(nemik.jsonarena) so the pinned Codon compiles them. `render` reads the field manifest through the
total parser and returns one line per published schema, the path, a tab and the compact JSON, with
a last line for openapi.json; key order is the order the dicts had, so the text equals
`json.dumps` of them. A malformed manifest raises ValueError: text that is not strict JSON,
trailing text, a missing section, a section that is not an object, or an unknown class.
"""

from nemik.jsonarena import Tree
from nemik.jsonparse import Parser

DIALECT = "https://json-schema.org/draft/2020-12/schema"
NULLABLE = {
    "ref": "string",
    "time": "string",
    "count": "number",
    "record": "object",
}
PLAIN = {"enum": "string", "text": "string", "flag": "boolean"}
LIST_PREFIX = "list-"
SCHEMA_DIR = "schema/"
SCHEMA_SUFFIX = ".schema.json"
PUBLISHED = ["graph.json", "wake.json", "history.json"]
FLAT = {"goals/<repo>.json": "goals", "umbrellas.json": "umbrellas"}


def kind(t: Tree, name: str) -> int:
    """Add the schema `{"type": name}`.

    Returns:
        The node's index.

    """
    return t.obj(["type"], [t.string(name)])


def kinds(t: Tree, names: list[str]) -> int:
    """Add the schema whose type is a list of names.

    Returns:
        The node's index.

    """
    return t.obj(["type"], [t.array([t.string(n) for n in names])])


def array_of(t: Tree, items: int) -> int:
    """Add an array schema over an item schema.

    Returns:
        The node's index.

    """
    return t.obj(["type", "items"], [t.string("array"), items])


def scalar(t: Tree, cls: str) -> int:
    """Add the schema of a scalar field class.

    Returns:
        The node's index.

    Raises:
        ValueError: the manifest names a class its vocabulary does not have.

    """
    if cls in NULLABLE:
        return kinds(t, [NULLABLE[cls], "null"])
    if cls in PLAIN:
        return kind(t, PLAIN[cls])
    if cls == "counts":
        extra = kind(t, "number")
        return t.obj(["type", "additionalProperties"], [t.string("object"), extra])
    if cls == "records":
        return array_of(t, kind(t, "object"))
    msg = "manifest: unknown field class " + cls
    raise ValueError(msg)


def field(t: Tree, cls: str) -> int:
    """Add the schema of one field class; `list-X` is an array of X.

    Returns:
        The node's index.

    """
    if cls.startswith(LIST_PREFIX):
        return array_of(t, field(t, cls[len(LIST_PREFIX) :]))
    return scalar(t, cls)


def sorted_fields(names: list[str], classes: list[str]) -> tuple[list[str], list[str]]:
    """Order a record's fields by name, as the manifest dict was sorted.

    Returns:
        The names and their classes, both in name order.

    """
    keys = sorted(names)
    return keys, [classes[names.index(k)] for k in keys]


def closed_object(t: Tree, props: int) -> int:
    """Add an object schema that allows only the given properties.

    Returns:
        The node's index.

    """
    return t.obj(
        ["type", "properties", "additionalProperties"],
        [t.string("object"), props, t.false()],
    )


def record(t: Tree, names: list[str], classes: list[str]) -> int:
    """Add the schema of a record: only the manifest's fields, none required.

    Returns:
        The node's index.

    """
    keys, sorted_classes = sorted_fields(names, classes)
    return closed_object(t, t.obj(keys, [field(t, c) for c in sorted_classes]))


def member(t: Tree, at: int, key: str) -> int:
    """Find the child of an object node by key.

    Returns:
        The child's index.

    Raises:
        ValueError: the node has no such key (or is not an object): a manifest missing a section
            is refused, where index -1 would have read the last node in the arena.

    """
    v = t.nodes[at]
    for i in range(len(v.keys)):
        if v.keys[i] == key:
            return v.kids[i]
    msg = "manifest: missing " + key
    raise ValueError(msg)


def fields_of(t: Tree, at: int) -> tuple[list[str], list[str]]:
    """Read a manifest section: its field names and their class names.

    Returns:
        The names and the classes, in the section's order.

    Raises:
        ValueError: the section is not an object, which the old module refused as well.

    """
    v = t.nodes[at]
    if v.kind != "object":
        msg = "manifest: a section is not an object"
        raise ValueError(msg)
    return list(v.keys), [t.nodes[k].text for k in v.kids]


def record_of(t: Tree, at: int) -> int:
    """Add the record schema of a manifest section.

    Returns:
        The node's index.

    """
    names, classes = fields_of(t, at)
    return record(t, names, classes)


def list_of(t: Tree, at: int) -> int:
    """Add the schema of a flat list of a section's records.

    Returns:
        The node's index.

    """
    return array_of(t, record_of(t, at))


def by_repo(t: Tree, value: int) -> int:
    """Add an object schema whose every value is the given schema.

    Returns:
        The node's index.

    """
    return t.obj(["type", "additionalProperties"], [t.string("object"), value])


def waiting(t: Tree, fields: int, wait: int) -> int:
    """Add a record whose properties also carry `waiting`, a list of the waiting records.

    Returns:
        The node's index. An existing `waiting` field keeps its place and takes the new value.

    """
    names, classes = fields_of(t, fields)
    keys, sorted_classes = sorted_fields(names, classes)
    kids = [field(t, c) for c in sorted_classes]
    if "waiting" in keys:
        kids[keys.index("waiting")] = list_of(t, wait)
    else:
        keys.append("waiting")
        kids.append(list_of(t, wait))
    return closed_object(t, t.obj(keys, kids))


def findings(t: Tree) -> int:
    """Add the schema of one repo's findings: a list of lists of strings.

    Returns:
        The node's index.

    """
    return array_of(t, array_of(t, kind(t, "string")))


def graph_schema(t: Tree, g: int) -> int:
    """Add the body of graph.json's schema from its manifest section.

    Returns:
        The node's index.

    """
    sections = ["nodes", "edges", "inbound", "operator"]
    keys = [*sections, "findings", "health", "ruler"]
    kids = [list_of(t, member(t, g, s)) for s in sections]
    kids.extend(
        [
            by_repo(t, findings(t)),
            by_repo(t, record_of(t, member(t, g, "health"))),
            record_of(t, member(t, g, "ruler")),
        ]
    )
    props = t.obj(keys, kids)
    return t.obj(
        ["type", "properties", "required", "additionalProperties"],
        [
            t.string("object"),
            props,
            t.array([t.string("nodes"), t.string("edges")]),
            t.false(),
        ],
    )


def wake_schema(t: Tree, w: int) -> int:
    """Add the body of wake.json's schema from its manifest section.

    Returns:
        The node's index.

    """
    live = t.nodes[member(t, member(t, w, "top"), "liveness")].text
    wait = member(t, w, "waiting")
    roster = array_of(t, waiting(t, member(t, w, "roster"), wait))
    props = t.obj(
        ["liveness", "series", "roster", "operator"],
        [
            field(t, live),
            kinds(t, ["object", "null"]),
            roster,
            waiting(t, member(t, w, "operator"), wait),
        ],
    )
    return closed_object(t, props)


def with_head(t: Tree, path: str, version: str, body: int) -> int:
    """Put the `$schema`, `$id` and `title` keys in front of a schema body.

    Returns:
        The node's index.

    """
    ident = "https://nemik/schema/v" + version + "/" + path.replace("<repo>", "{repo}")
    head = [t.string(DIALECT), t.string(ident), t.string("nemik " + path)]
    node = t.nodes[body]
    return t.obj(["$schema", "$id", "title", *node.keys], [*head, *node.kids])


def version_text(t: Tree, doc: int) -> str:
    """Read the manifest's version, kept as written.

    Returns:
        The version's source text.

    """
    return t.nodes[member(t, doc, "version")].text


def schemas(t: Tree, doc: int) -> tuple[list[str], list[int]]:
    """Build every published schema from the manifest document.

    Returns:
        The published paths and, beside them, each schema's node index.

    """
    files = member(t, doc, "files")
    version = version_text(t, doc)
    history = by_repo(
        t, list_of(t, member(t, member(t, files, "history.json"), "weeks"))
    )
    bodies = [
        graph_schema(t, member(t, files, "graph.json")),
        wake_schema(t, member(t, files, "wake.json")),
        history,
    ]
    paths = list(PUBLISHED)
    for path, section in FLAT.items():
        paths.append(path)
        bodies.append(list_of(t, member(t, member(t, files, path), section)))
    heads = [with_head(t, paths[i], version, bodies[i]) for i in range(len(paths))]
    return paths, heads


def schema_path(pattern: str) -> str:
    """Name where the static build publishes a schema.

    Returns:
        The path under schema/, `<repo>` written as `repo`, with a .schema.json suffix.

    """
    return SCHEMA_DIR + pattern.replace("<repo>", "repo") + SCHEMA_SUFFIX


def get_op(t: Tree, summary: str, schema: int, param: str) -> int:
    """Add a GET operation whose 200 response is the given schema.

    Returns:
        The node's index. A non-empty `param` adds a required path parameter.

    """
    content = t.obj(["application/json"], [t.obj(["schema"], [schema])])
    response = t.obj(["description", "content"], [t.string("the document"), content])
    keys = ["summary", "responses"]
    kids = [t.string(summary), t.obj(["200"], [response])]
    if param:
        parameter = t.obj(
            ["name", "in", "required", "schema"],
            [t.string(param), t.string("path"), t.true(), kind(t, "string")],
        )
        keys.append("parameters")
        kids.append(t.array([parameter]))
    return t.obj(["get"], [t.obj(keys, kids)])


def openapi_paths(t: Tree, patterns: list[str]) -> int:
    """Add the openapi `paths` object: one GET per schema, then the two fixed ones.

    Returns:
        The node's index.

    """
    urls: list[str] = []
    ops: list[int] = []
    for pattern in patterns:
        urls.append("/" + pattern.replace("<repo>", "{repo}"))
        ref = t.obj(["$ref"], [t.string(schema_path(pattern))])
        ops.append(
            get_op(t, "nemik " + pattern, ref, "repo" if "<repo>" in pattern else "")
        )
    hashes = by_repo(t, kind(t, "string"))
    moved = "every published path with the sha256 of its bytes (W414): refetch only what moved"
    one_piece = "one repo's piece of graph.json, or _fleet (W415); assembling them gives graph.json"
    urls.extend(["/hashes.json", "/graph/{piece}.json"])
    ops.extend(
        [
            get_op(t, moved, hashes, ""),
            get_op(t, one_piece, kind(t, "object"), "piece"),
        ]
    )
    return t.obj(urls, ops)


def openapi(t: Tree, doc: int, patterns: list[str]) -> int:
    """Add the OpenAPI 3.1 document for the read API.

    Returns:
        The node's index.

    """
    description = (
        "Read-only. Every document is a static file; the field manifest is the "
        "contract, and a field outside it fails nemik's build."
    )
    info = t.obj(
        ["title", "version", "description"],
        [
            t.string("nemik read API"),
            t.string(version_text(t, doc)),
            t.string(description),
        ],
    )
    return t.obj(
        ["openapi", "info", "jsonSchemaDialect", "paths"],
        [t.string("3.1.0"), info, t.string(DIALECT), openapi_paths(t, patterns)],
    )


def render(manifest_text: str) -> list[str]:
    """Build every schema and the openapi document from the manifest's text.

    Returns:
        One `<path>` TAB `<compact JSON>` line per schema, and a last one for openapi.json.

    Raises:
        ValueError: the text is not strict JSON, or the manifest lacks a section or names a class
            its vocabulary does not have.

    """
    p = Parser(manifest_text)
    doc = p.value()
    p.skip()
    if p.ok and p.pos != len(manifest_text):
        p.fail()
    if not p.ok or doc < 0:
        msg = "manifest: not strict JSON, first failure at " + str(p.fail_at)
        raise ValueError(msg)
    t = p.tree
    paths, bodies = schemas(t, doc)
    lines = [paths[i] + "\t" + t.dump(bodies[i]) for i in range(len(paths))]
    lines.append("openapi.json\t" + t.dump(openapi(t, doc, paths)))
    return lines
