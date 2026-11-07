# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: a JSON value tree the pinned Codon compiles, held as an arena of indexed nodes.

A value is a `Val` in a `Tree`'s `nodes`, and a container names its children by index, so no
annotation names a class before it exists (a class-level self-reference is a NameError on 3.13, and
fields annotated only inside `__init__` are refused by Codon). `Tree.dump` writes compact JSON
exactly as `json.dumps(value, separators=(",", ":"))` does: ASCII-only, DEL and non-ASCII escaped,
astral characters as surrogate pairs. A number keeps its source text.
"""

HEX = "0123456789abcdef"
ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\b": "\\b",
    "\f": "\\f",
}
FIRST_ASTRAL = 65536
SURROGATE_HIGH = 55296
SURROGATE_LOW = 56320
LAST_RAW = 126
FIRST_PRINTABLE = 32


class Val:
    """One node: a kind, a text or flag for a leaf, and child indexes and names for a container."""

    kind: str
    text: str
    flag: bool
    kids: list[int]
    keys: list[str]

    def __init__(self, kind: str) -> None:
        """Make an empty node of a kind."""
        self.kind = kind
        self.text = ""
        self.flag = False
        self.kids = []
        self.keys = []


def hex4(code: int) -> str:
    """Write a code unit as a JSON unicode escape: a backslash, u and four hex digits.

    Returns:
        The six-character escape, lower-case hexadecimal.

    """
    digits = HEX[(code >> 12) & 15] + HEX[(code >> 8) & 15] + HEX[(code >> 4) & 15]
    return "\\u" + digits + HEX[code & 15]


def escape_char(ch: str) -> str:
    """Escape one character the way json.dumps does with ensure_ascii.

    Returns:
        The character itself when it is printable ASCII, else its escape.

    """
    code = ord(ch)
    if ch in ESCAPES:
        return ESCAPES[ch]
    if FIRST_PRINTABLE <= code <= LAST_RAW:
        return ch
    if code < FIRST_ASTRAL:
        return hex4(code)
    low = code - FIRST_ASTRAL
    return hex4(SURROGATE_HIGH + (low >> 10)) + hex4(SURROGATE_LOW + (low & 1023))


def escape(text: str) -> str:
    """Escape a string for the inside of a JSON string literal.

    Returns:
        The text with every character that json.dumps escapes escaped.

    """
    out = ""
    for ch in text:
        out += escape_char(ch)
    return out


class Tree:
    """An arena of nodes: build values with the methods below, then dump one by its index."""

    nodes: list[Val]

    def __init__(self) -> None:
        """Make an empty arena."""
        self.nodes = []

    def add(self, v: Val) -> int:
        """Put a node in the arena.

        Returns:
            The node's index.

        """
        self.nodes.append(v)
        return len(self.nodes) - 1

    def string(self, text: str) -> int:
        """Add a string node.

        Returns:
            The node's index.

        """
        v = Val("str")
        v.text = text
        return self.add(v)

    def true(self) -> int:
        """Add a true node.

        Returns:
            The node's index.

        """
        v = Val("bool")
        v.flag = True
        return self.add(v)

    def false(self) -> int:
        """Add a false node.

        Returns:
            The node's index.

        """
        v = Val("bool")
        v.flag = False
        return self.add(v)

    def array(self, kids: list[int]) -> int:
        """Add an array node over child indexes.

        Returns:
            The node's index.

        """
        v = Val("array")
        v.kids = kids
        return self.add(v)

    def obj(self, keys: list[str], kids: list[int]) -> int:
        """Add an object node: one key per child index, in the order given.

        Returns:
            The node's index.

        """
        v = Val("object")
        v.keys = keys
        v.kids = kids
        return self.add(v)

    def dump(self, at: int) -> str:
        """Write the value at an index as compact JSON.

        Returns:
            The JSON text.

        """
        v = self.nodes[at]
        if v.kind == "str":
            return '"' + escape(v.text) + '"'
        if v.kind == "bool":
            return "true" if v.flag else "false"
        if v.kind == "null":
            return "null"
        if v.kind == "number":
            return v.text
        if v.kind == "array":
            return "[" + ",".join([self.dump(k) for k in v.kids]) + "]"
        pairs = [
            '"' + escape(v.keys[j]) + '":' + self.dump(v.kids[j])
            for j in range(len(v.keys))
        ]
        return "{" + ",".join(pairs) + "}"
