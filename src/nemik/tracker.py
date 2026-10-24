# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""tracker: a tracker's issue as its API sends it, read into a mirror's fields (nemik:W957).

W369 mirrors cards to an issue tracker and W370 reads a tracker's events. Both start from what a
tracker really sends: a nested JSON object (a `user` object, a list of `labels` objects, nulls). The
standard json module answers with Any, which the house type check refuses to count, so this reads
the text itself into a recursive typed value and then picks fields out of it. The two fixtures in
tests/fixtures/trackers/ (a GitHub issue and a Forgejo issue, recorded unedited) are what it is
tested on.

Both trackers say the same things under different keys; the differences found in those files are
handled here: GitHub's `locked` is Forgejo's `is_locked`, and GitHub's issues endpoint also returns
pull requests, marked by a `pull_request` object (Forgejo sends `pull_request: null` for an issue).
Text that is not JSON raises ValueError; JSON of the wrong shape raises TypeError.
"""

from typing import NamedTuple, NoReturn

type Json = str | int | float | bool | list[Json] | dict[str, Json] | None

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
WORDS: dict[str, Json] = {"true": True, "false": False, "null": None}
SPACE = " \t\r\n"
NUMBER_CHARS = "+-.eE0123456789"
HEX_DIGITS = 4
HIGH_SURROGATES = range(0xD800, 0xDC00)
LOW_SURROGATES = range(0xDC00, 0xE000)


class Issue(NamedTuple):
    """One issue, as far as a mirror reads it."""

    number: int
    title: str
    state: str
    body: str
    labels: list[str]
    url: str
    is_pull_request: bool
    locked: bool


class _Reader:
    """A cursor over JSON text."""

    def __init__(self, text: str) -> None:
        """Hold the text and start at its first character."""
        self.text = text
        self.at = 0

    def fail(self, why: str) -> NoReturn:
        """Say where the text stopped making sense.

        Args:
            why: What was wrong.

        Raises:
            ValueError: Always, naming the offset.

        """
        message = f"{why} at offset {self.at}"
        raise ValueError(message)

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
            self.fail(f"expected {char}")
        self.at += 1

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
            self.fail("a bad unicode escape")
        self.at += HEX_DIGITS
        return value

    def unicode(self) -> str:
        """Read the four hex digits after a backslash-u, joining a surrogate pair.

        Returns:
            The character.

        """
        code = self.hex4()
        if code in HIGH_SURROGATES:
            if not self.text.startswith("\\u", self.at):
                self.fail("a high surrogate without its pair")
            self.at += 2
            low = self.hex4()
            if low not in LOW_SURROGATES:
                self.fail("a high surrogate without its low half")
            code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
        elif code in LOW_SURROGATES:
            self.fail("a lone low surrogate")
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
                self.fail("a bad escape")
        return self.fail("an unclosed string")

    def number(self) -> int | float:
        """Read a number.

        Returns:
            An int when it has no fraction or exponent, else a float.

        """
        start = self.at
        while self.at < len(self.text) and self.text[self.at] in NUMBER_CHARS:
            self.at += 1
        raw = self.text[start : self.at]
        try:
            return int(raw) if raw.lstrip("-").isdigit() else float(raw)
        except ValueError:
            return self.fail("a bad number")

    def array(self) -> list[Json]:
        """Read an array.

        Returns:
            Its items.

        """
        self.expect("[")
        items: list[Json] = []
        if self.peek() == "]":
            self.at += 1
            return items
        while True:
            items.append(self.value())
            if self.peek() == ",":
                self.at += 1
                continue
            self.expect("]")
            return items

    def mapping(self) -> dict[str, Json]:
        """Read an object.

        Returns:
            Its members.

        """
        self.expect("{")
        members: dict[str, Json] = {}
        if self.peek() == "}":
            self.at += 1
            return members
        while True:
            self.peek()
            key = self.string()
            self.expect(":")
            members[key] = self.value()
            if self.peek() == ",":
                self.at += 1
                continue
            self.expect("}")
            return members

    def value(self) -> Json:
        """Read one value.

        Returns:
            It, typed.

        """
        char = self.peek()
        if char == "{":
            return self.mapping()
        if char == "[":
            return self.array()
        if char == '"':
            return self.string()
        for word, meant in WORDS.items():
            if self.text.startswith(word, self.at):
                self.at += len(word)
                return meant
        if char and char in NUMBER_CHARS:
            return self.number()
        return self.fail("not a JSON value")


def parse(text: str) -> Json:
    """Read JSON text into a typed value.

    Args:
        text: One JSON value, as a tracker's API sent it.

    Returns:
        The value: strings, numbers, booleans, None, lists and dicts of them. Text that is not
        exactly one JSON value raises ValueError.

    """
    reader = _Reader(text)
    got = reader.value()
    if reader.peek():
        reader.fail("text after the value")
    return got


def _text(item: dict[str, Json], key: str) -> str:
    """Read a string member, empty when it is absent or null.

    Returns:
        The string.

    Raises:
        TypeError: When the member is something other than a string or null.

    """
    got = item.get(key)
    if got is None:
        return ""
    if isinstance(got, str):
        return got
    message = f"{key} is not a string"
    raise TypeError(message)


def _flag(item: dict[str, Json], key: str) -> bool:
    """Read a boolean member, false when it is absent or null.

    Returns:
        The flag.

    Raises:
        TypeError: When the member is something other than a boolean or null.

    """
    got = item.get(key)
    if got is None:
        return False
    if isinstance(got, bool):
        return got
    message = f"{key} is not a boolean"
    raise TypeError(message)


def _label_names(item: dict[str, Json]) -> list[str]:
    """Read the names of an issue's labels.

    Returns:
        Each label's `name`, in the tracker's order; none when the member is absent or null.

    Raises:
        TypeError: When `labels` is not a list of objects with a string name.

    """
    got = item.get("labels")
    if got is None:
        return []
    if not isinstance(got, list):
        message = "labels is not a list"
        raise TypeError(message)
    names: list[str] = []
    for label in got:
        if not isinstance(label, dict):
            message = "a label is not an object"
            raise TypeError(message)
        name = label.get("name")
        if not isinstance(name, str):
            message = "a label has no string name"
            raise TypeError(message)
        names.append(name)
    return names


def read_issue(text: str) -> Issue:
    """Read one tracker issue.

    Args:
        text: The JSON a GitHub or Forgejo issue endpoint answered; text that is not JSON raises
            ValueError.

    Returns:
        The issue's number, title, state, body, label names, url, whether it is a pull request and
        whether it is locked.

    Raises:
        TypeError: When the JSON is not an issue object or a field has the wrong type.

    """
    item = parse(text)
    if not isinstance(item, dict):
        message = "an issue is a JSON object"
        raise TypeError(message)
    number = item.get("number")
    if not isinstance(number, int) or isinstance(number, bool):
        message = "an issue has an integer number"
        raise TypeError(message)
    return Issue(
        number,
        _text(item, "title"),
        _text(item, "state"),
        _text(item, "body"),
        _label_names(item),
        _text(item, "html_url"),
        item.get("pull_request") is not None,
        _flag(item, "locked") or _flag(item, "is_locked"),
    )
