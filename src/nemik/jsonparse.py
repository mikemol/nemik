# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: a total JSON parser into the arena tree, compilable by the pinned Codon.

`parse` returns the compact JSON of the document, or the word `error` when it is not strict RFC 8259
JSON. It never indexes past the end of the text (`peek` returns an empty string there) and keeps the
first failure position in `fail_at`. A number keeps its source text, so `1e3` stays `1e3`. Differs
from `json.loads` in refusing NaN and the infinities.
"""

from nemik.jsonarena import Tree, Val

HEXDIGITS = "0123456789abcdef"
SPACE = " \t\r\n"
SIMPLE = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    '"': '"',
    "\\": "\\",
    "/": "/",
}
FIRST_HIGH = 55296
FIRST_LOW = 56320
FIRST_AFTER_LOW = 57344
FIRST_ASTRAL = 65536
NEXT_ESCAPE = 2
FIRST_PRINTABLE = 32


class Parser:
    """A cursor over the text with the tree it builds and the first failure, if any."""

    text: str
    pos: int
    ok: bool
    fail_at: int
    tree: Tree

    def __init__(self, text: str) -> None:
        """Start at the beginning of a text with an empty tree."""
        self.text = text
        self.pos = 0
        self.ok = True
        self.fail_at = -1
        self.tree = Tree()

    def fail(self) -> int:
        """Record the first failure at the cursor.

        Returns:
            -1, the index no node has.

        """
        if self.ok:
            self.ok = False
            self.fail_at = self.pos
        return -1

    def peek(self) -> str:
        """Look at the character under the cursor.

        Returns:
            The character, or an empty string at the end.

        """
        if self.pos < len(self.text):
            return self.text[self.pos]
        return ""

    def skip(self) -> None:
        """Move the cursor over JSON whitespace."""
        while self.peek() and self.peek() in SPACE:
            self.pos += 1

    def quad(self) -> int:
        """Read four hex digits.

        Returns:
            Their value, or 0 after recording a failure.

        """
        code = 0
        for _ in range(4):
            at = HEXDIGITS.find(self.peek().lower()) if self.peek() else -1
            if at < 0:
                self.fail()
                return 0
            code = code * 16 + at
            self.pos += 1
        return code

    def unicode_escape(self) -> str:
        """Read the four digits after a backslash-u, joining a surrogate pair.

        Returns:
            The decoded character. A lone surrogate is kept as it is, as json.loads does.

        """
        code = self.quad()
        if (
            FIRST_HIGH <= code < FIRST_LOW
            and self.text[self.pos : self.pos + 2] == "\\u"
        ):
            save = self.pos
            self.pos += NEXT_ESCAPE
            low = self.quad()
            if FIRST_LOW <= low < FIRST_AFTER_LOW:
                code = FIRST_ASTRAL + ((code - FIRST_HIGH) << 10) + (low - FIRST_LOW)
            else:
                self.pos = save
        return chr(code)

    def escaped(self) -> str:
        """Read the character after a backslash.

        Returns:
            The decoded character, or an empty string after recording a failure.

        """
        esc = self.peek()
        if not esc:
            self.fail()
            return ""
        self.pos += 1
        if esc in SIMPLE:
            return SIMPLE[esc]
        if esc == "u":
            return self.unicode_escape()
        self.pos -= 1
        self.fail()
        return ""

    def string_text(self) -> str:
        """Read a string literal.

        Returns:
            The decoded text, or an empty string after recording a failure.

        """
        if self.peek() != '"':
            self.fail()
            return ""
        self.pos += 1
        out = ""
        while self.ok:
            ch = self.peek()
            if not ch or (ch != '"' and ord(ch) < FIRST_PRINTABLE):
                self.fail()
                return ""
            self.pos += 1
            if ch == '"':
                return out
            out += self.escaped() if ch == "\\" else ch
        return ""

    def digits(self) -> int:
        """Move over a run of digits.

        Returns:
            How many there were.

        """
        n = 0
        while self.peek() and "0" <= self.peek() <= "9":
            self.pos += 1
            n += 1
        return n

    def fraction(self) -> bool:
        """Read an optional fraction and exponent.

        Returns:
            False after recording a failure.

        """
        if self.peek() == ".":
            self.pos += 1
            if self.digits() == 0:
                self.fail()
                return False
        if self.peek() == "e" or self.peek() == "E":
            self.pos += 1
            if self.peek() == "+" or self.peek() == "-":
                self.pos += 1
            if self.digits() == 0:
                self.fail()
                return False
        return True

    def number(self) -> int:
        """Read a number, keeping its source text.

        Returns:
            The node's index, or -1 after recording a failure.

        """
        start = self.pos
        if self.peek() == "-":
            self.pos += 1
        if self.peek() == "0":
            self.pos += 1
        elif self.digits() == 0:
            return self.fail()
        if not self.fraction():
            return -1
        v = Val("number")
        v.text = self.text[start : self.pos]
        return self.tree.add(v)

    def word(self, literal: str) -> bool:
        """Consume a literal word.

        Returns:
            False after recording a failure when the text does not hold it here.

        """
        if self.text[self.pos : self.pos + len(literal)] != literal:
            self.fail()
            return False
        self.pos += len(literal)
        return True

    def array(self) -> int:
        """Read an array, the cursor on its opening bracket.

        Returns:
            The node's index, or -1 after recording a failure.

        """
        self.pos += 1
        kids: list[int] = []
        self.skip()
        if self.peek() == "]":
            self.pos += 1
            return self.tree.array(kids)
        while True:
            kid = self.value()
            if not self.ok:
                return -1
            kids.append(kid)
            self.skip()
            if self.peek() == ",":
                self.pos += 1
                continue
            if self.peek() == "]":
                self.pos += 1
                return self.tree.array(kids)
            return self.fail()

    def member(self, keys: list[str], kids: list[int]) -> bool:
        """Read one key and value into the lists.

        Returns:
            False after recording a failure.

        """
        self.skip()
        key = self.string_text()
        if not self.ok:
            return False
        self.skip()
        if self.peek() != ":":
            self.fail()
            return False
        self.pos += 1
        kid = self.value()
        if kid < 0:
            return False
        keys.append(key)
        kids.append(kid)
        return True

    def object(self) -> int:
        """Read an object, the cursor on its opening brace.

        Returns:
            The node's index, or -1 after recording a failure.

        """
        self.pos += 1
        keys: list[str] = []
        kids: list[int] = []
        self.skip()
        if self.peek() == "}":
            self.pos += 1
            return self.tree.obj(keys, kids)
        while True:
            if not self.member(keys, kids):
                return -1
            self.skip()
            if self.peek() == ",":
                self.pos += 1
                continue
            if self.peek() == "}":
                self.pos += 1
                return self.tree.obj(keys, kids)
            return self.fail()

    def literal_value(self, lead: str) -> int:
        """Read true, false or null from its first letter.

        Returns:
            The node's index, or -1 after recording a failure.

        """
        if lead == "t":
            return self.tree.true() if self.word("true") else -1
        if lead == "f":
            return self.tree.false() if self.word("false") else -1
        return self.tree.add(Val("null")) if self.word("null") else -1

    def value(self) -> int:
        """Read any value at the cursor.

        Returns:
            The node's index, or -1 after recording a failure.

        """
        self.skip()
        lead = self.peek()
        if not lead:
            return self.fail()
        if lead == "{":
            return self.object()
        if lead == "[":
            return self.array()
        if lead == '"':
            text = self.string_text()
            return self.tree.string(text) if self.ok else -1
        if lead in "tfn":
            return self.literal_value(lead)
        return self.number()


def parse(text: str) -> str:
    """Parse a whole document and write it back as compact JSON.

    Returns:
        The compact JSON, or the word error when the text is not strict JSON.

    """
    p = Parser(text)
    at = p.value()
    p.skip()
    if p.ok and p.pos != len(text):
        p.fail()
    if not p.ok:
        return "error"
    return p.tree.dump(at)
