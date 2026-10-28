# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""tracker: a tracker's issue as its API sends it, read into a mirror's fields (nemik:W957).

W369 mirrors cards to an issue tracker and W370 reads a tracker's events. Both start from what a
tracker really sends: a nested JSON object (a `user` object, a list of `labels` objects, nulls). The
standard json module answers with Any, which the house type check refuses to count, so this reads
the text itself into a `Tree` and then picks fields out of it. A tree of parallel arrays addressed
by integer handles, and not a recursive alias or a class that holds itself, because Codon compiles
neither and CPython 3.13 refuses the class that holds itself without the annotations future that
Codon refuses in turn (nemik:W1034). The two fixtures in tests/fixtures/trackers/ (a GitHub issue
and a Forgejo issue, recorded unedited) are what it is tested on.

Both trackers say the same things under different keys; the differences found in those files are
handled here: GitHub's `locked` is Forgejo's `is_locked`, and GitHub's issues endpoint also returns
pull requests, marked by a `pull_request` object (Forgejo sends `pull_request: null` for an issue).
Text that is not JSON raises ValueError; JSON of the wrong shape raises TypeError.
"""

NULL, BOOL, INT, REAL, STR, LIST, DICT = 0, 1, 2, 3, 4, 5, 6
MISSING = 0  # the handle of the one null value every absent member reads as

ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}
SPACE = " \t\r\n"
NUMBER_CHARS = "+-.eE0123456789"
HEX_DIGITS = 4
HIGH_SURROGATES = range(0xD800, 0xDC00)
LOW_SURROGATES = range(0xDC00, 0xE000)


class Tree:
    """Parsed JSON as parallel arrays: a value is an integer, its index in each of them.

    Handle 0 is a null that stands for every member that is not there. `root` is the handle of the
    value the whole text held.
    """

    kinds: list[int]
    flags: list[bool]
    wholes: list[int]
    reals: list[float]
    texts: list[str]
    kids: list[list[int]]
    names: list[list[str]]
    root: int

    def __init__(self) -> None:
        """Make a tree holding only the null at handle 0."""
        self.kinds = []
        self.flags = []
        self.wholes = []
        self.reals = []
        self.texts = []
        self.kids = []
        self.names = []
        self.root = 0
        self.add(NULL)

    def add(self, kind: int) -> int:
        """Append an empty value of a kind (NULL, BOOL, INT, REAL, STR, LIST or DICT).

        Returns:
            Its handle.

        """
        self.kinds.append(kind)
        self.flags.append(False)
        self.wholes.append(0)
        self.reals.append(0.0)
        self.texts.append("")
        self.kids.append([])
        self.names.append([])
        return len(self.kinds) - 1

    def get(self, at: int, key: str) -> int:
        """Look a member up by name.

        Args:
            at: The handle of an object.
            key: The member's name.

        Returns:
            The member's handle (the last one when the name repeats); MISSING when `at` is not an
            object or has no such member, since a missing member and a null one read alike here.

        """
        names = self.names[at]
        place = len(names) - 1
        while place >= 0:
            if names[place] == key:
                return self.kids[at][place]
            place -= 1
        return MISSING

    def string(self, at: int, key: str) -> str:
        """Read a member that is a string.

        Args:
            at: The handle of an object.
            key: The member's name.

        Returns:
            The string; empty when the member is missing, null or not a string.

        """
        member = self.get(at, key)
        return self.texts[member] if self.kinds[member] == STR else ""


class Issue:
    """One issue, as far as a mirror reads it.

    A plain class and not a NamedTuple, which Codon will not make a reference class of: the
    fields are set after construction.
    """

    number: int
    title: str
    state: str
    body: str
    labels: list[str]
    url: str
    is_pull_request: bool
    locked: bool

    def __init__(self, number: int) -> None:
        """Make an issue with its number and the other fields empty."""
        self.number = number
        self.title = ""
        self.state = ""
        self.body = ""
        self.labels = []
        self.url = ""
        self.is_pull_request = False
        self.locked = False


class _Reader:
    """A cursor over JSON text, building a Tree."""

    def __init__(self, text: str) -> None:
        """Hold the text and start at its first character."""
        self.text = text
        self.at = 0
        self.tree = Tree()

    def error(self, why: str) -> ValueError:
        """Say where the text stopped making sense.

        Args:
            why: What was wrong.

        Returns:
            The ValueError to raise, naming the offset.

        """
        return ValueError(f"{why} at offset {self.at}")

    def peek(self) -> str:
        """Look at the next character after whitespace.

        Returns:
            The character, or an empty string at the end.

        """
        while self.at < len(self.text) and self.text[self.at] in SPACE:
            self.at += 1
        return self.text[self.at : self.at + 1]

    def expect(self, char: str) -> None:
        """Take one character that must be next."""
        if self.peek() != char:
            message = f"expected {char}"
            raise self.error(message)
        self.at += 1

    def word(self, spelled: str) -> bool:
        """Take a bare word if it is next.

        Returns:
            Whether it was there; the cursor moves past it when it was.

        """
        end = self.at + len(spelled)
        if self.text[self.at : end] != spelled:
            return False
        self.at = end
        return True

    def hex4(self) -> int:
        """Read four hex digits.

        Returns:
            Their value.

        """
        digits = self.text[self.at : self.at + HEX_DIGITS]
        try:
            value = int(digits, 16) if len(digits) == HEX_DIGITS else -1
        except ValueError:
            value = -1
        if value < 0:
            message = "a bad unicode escape"
            raise self.error(message)
        self.at += HEX_DIGITS
        return value

    def unicode(self) -> str:
        """Read the four hex digits after a backslash-u, joining a surrogate pair.

        Returns:
            The character.

        """
        code = self.hex4()
        if code in HIGH_SURROGATES:
            if self.text[self.at : self.at + 2] != "\\u":
                message = "a high surrogate without its pair"
                raise self.error(message)
            self.at += 2
            low = self.hex4()
            if low not in LOW_SURROGATES:
                message = "a high surrogate without its low half"
                raise self.error(message)
            code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
        elif code in LOW_SURROGATES:
            message = "a lone low surrogate"
            raise self.error(message)
        return chr(code)

    def string(self) -> str:
        """Read a string literal.

        Returns:
            Its text, escapes resolved.

        """
        self.expect('"')
        out: list[str] = []
        while self.at < len(self.text):
            char = self.text[self.at]
            self.at += 1
            if char == '"':
                return "".join(out)
            if char != "\\":
                out.append(char)
                continue
            key = self.text[self.at : self.at + 1]
            self.at += 1
            if key == "u":
                out.append(self.unicode())
            elif key in ESCAPES:
                out.append(ESCAPES[key])
            else:
                message = "a bad escape"
                raise self.error(message)
        message = "an unclosed string"
        raise self.error(message)

    def number(self) -> int:
        """Read a number.

        Returns:
            The handle of an INT value when it has no fraction or exponent, else a REAL one.

        """
        start = self.at
        while self.at < len(self.text) and self.text[self.at] in NUMBER_CHARS:
            self.at += 1
        raw = self.text[start : self.at]
        node = self.tree.add(INT if raw.lstrip("-").isdigit() else REAL)
        try:
            if self.tree.kinds[node] == INT:
                self.tree.wholes[node] = int(raw)
            else:
                self.tree.reals[node] = float(raw)
        except ValueError as e:
            # nemik:W1179: `from None` makes the pinned Codon fail to typecheck this method in
            # reasonable time as soon as a program calls parse_tree; `from e` compiles
            message = "a bad number"
            raise self.error(message) from e
        return node

    def array(self) -> int:
        """Read an array.

        Returns:
            The handle of a LIST value; its items are in `kids`.

        """
        self.expect("[")
        node = self.tree.add(LIST)
        if self.peek() == "]":
            self.at += 1
            return node
        while True:
            item = self.value()
            self.tree.kids[node].append(item)
            if self.peek() == ",":
                self.at += 1
                continue
            self.expect("]")
            return node

    def mapping(self) -> int:
        """Read an object.

        Returns:
            The handle of a DICT value: its member names in `names` and the values beside them in
            `kids`.

        """
        self.expect("{")
        node = self.tree.add(DICT)
        if self.peek() == "}":
            self.at += 1
            return node
        while True:
            self.peek()
            name = self.string()
            self.expect(":")
            member = self.value()
            self.tree.names[node].append(name)
            self.tree.kids[node].append(member)
            if self.peek() == ",":
                self.at += 1
                continue
            self.expect("}")
            return node

    def value(self) -> int:
        """Read one value.

        Returns:
            Its handle.

        """
        char = self.peek()
        if char == "{":
            return self.mapping()
        if char == "[":
            return self.array()
        node = MISSING
        if char == '"':
            node = self.tree.add(STR)
            self.tree.texts[node] = self.string()
        elif self.word("true") or self.word("false"):
            node = self.tree.add(BOOL)
            self.tree.flags[node] = self.text[self.at - 4 : self.at] == "true"
        elif self.word("null"):
            node = self.tree.add(NULL)
        elif char and char in NUMBER_CHARS:
            node = self.number()
        else:
            message = "not a JSON value"
            raise self.error(message)
        return node


def parse_tree(text: str) -> Tree:
    """Read JSON text into a tree.

    Args:
        text: One JSON value, as a tracker's API sent it.

    Returns:
        The tree, its `root` the handle of the value. Text that is not exactly one JSON value
        raises ValueError, naming the offset.

    """
    reader = _Reader(text)
    reader.tree.root = reader.value()
    if reader.peek():
        message = "text after the value"
        raise reader.error(message)
    return reader.tree


def _text(tree: Tree, item: int, key: str) -> str:
    """Read a string member, empty when it is absent or null.

    Returns:
        The string.

    Raises:
        TypeError: When the member is something other than a string or null.

    """
    got = tree.get(item, key)
    if tree.kinds[got] == NULL:
        return ""
    if tree.kinds[got] == STR:
        return tree.texts[got]
    message = f"{key} is not a string"
    raise TypeError(message)


def _flag(tree: Tree, item: int, key: str) -> bool:
    """Read a boolean member, false when it is absent or null.

    Returns:
        The flag.

    Raises:
        TypeError: When the member is something other than a boolean or null.

    """
    got = tree.get(item, key)
    if tree.kinds[got] == NULL:
        return False
    if tree.kinds[got] == BOOL:
        return tree.flags[got]
    message = f"{key} is not a boolean"
    raise TypeError(message)


def _label_names(tree: Tree, item: int) -> list[str]:
    """Read the names of an issue's labels.

    Returns:
        Each label's `name`, in the tracker's order; none when the member is absent or null.

    Raises:
        TypeError: When `labels` is not a list of objects with a string name.

    """
    got = tree.get(item, "labels")
    if tree.kinds[got] == NULL:
        return []
    if tree.kinds[got] != LIST:
        message = "labels is not a list"
        raise TypeError(message)
    names: list[str] = []
    for label in tree.kids[got]:
        if tree.kinds[label] != DICT:
            message = "a label is not an object"
            raise TypeError(message)
        name = tree.get(label, "name")
        if tree.kinds[name] != STR:
            message = "a label has no string name"
            raise TypeError(message)
        names.append(tree.texts[name])
    return names


def cite_of(body: str) -> str:
    """Find the card a mirrored issue stands for.

    Args:
        body: An issue's body; nemik.issues writes `nemik card <cite>` into every issue it mirrors.

    Returns:
        The cite after those words, or an empty string when the body does not say.

    """
    marker = "nemik card "
    at = body.find(marker)
    if at < 0:
        return ""
    words = body[at + len(marker) :].split()
    return words[0] if words else ""


def row_of(issue: Issue) -> dict[str, object]:
    """Give an issue as the row nemik.mirror compares against.

    Args:
        issue: A tracker issue.

    Returns:
        cite (from the body, empty for an issue nemik did not mirror), title, body, state and
        labels. There is no blocked_by: the issue payloads carry dependency counts only, so the
        field is unknown here, not empty.

    """
    return {
        "cite": cite_of(issue.body),
        "title": issue.title,
        "body": issue.body,
        "state": issue.state,
        "labels": list(issue.labels),
    }


def read_issues(text: str) -> list[Issue]:
    """Read a tracker's list of issues.

    Args:
        text: The JSON array a GitHub or Forgejo issues endpoint answered.

    Returns:
        The issues in the tracker's order; text that is not JSON raises ValueError.

    Raises:
        TypeError: When the JSON is not an array of issue objects.

    """
    tree = parse_tree(text)
    if tree.kinds[tree.root] != LIST:
        message = "a list of issues is a JSON array"
        raise TypeError(message)
    return [issue_of(tree, item) for item in tree.kids[tree.root]]


def read_issue(text: str) -> Issue:
    """Read one tracker issue.

    Args:
        text: The JSON a GitHub or Forgejo issue endpoint answered; text that is not JSON raises
            ValueError.

    Returns:
        The issue's number, title, state, body, label names, url, whether it is a pull request and
        whether it is locked.

    """
    tree = parse_tree(text)
    return issue_of(tree, tree.root)


def issue_of(tree: Tree, item: int) -> Issue:
    """Read one parsed tracker issue.

    Args:
        tree: The parsed JSON.
        item: The handle of the value to read.

    Returns:
        The issue's number, title, state, body, label names, url, whether it is a pull request and
        whether it is locked.

    Raises:
        TypeError: When the JSON is not an issue object or a field has the wrong type.

    """
    if tree.kinds[item] != DICT:
        message = "an issue is a JSON object"
        raise TypeError(message)
    number = tree.get(item, "number")
    if tree.kinds[number] != INT:
        message = "an issue has an integer number"
        raise TypeError(message)
    issue = Issue(tree.wholes[number])
    issue.title = _text(tree, item, "title")
    issue.state = _text(tree, item, "state")
    issue.body = _text(tree, item, "body")
    issue.labels = _label_names(tree, item)
    issue.url = _text(tree, item, "html_url")
    issue.is_pull_request = tree.kinds[tree.get(item, "pull_request")] != NULL
    issue.locked = _flag(tree, item, "locked") or _flag(tree, item, "is_locked")
    return issue
