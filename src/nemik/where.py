# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1128: a filter language over a card's row, shaped like find(1)'s predicates.

`nemik-history --oldest 20 --where 'status=ready and not blocked_on=* and age>2d'`. A predicate is
`field op value`; the fields are status, age, flag, repo, blocked_on and title; the operators are
`=`, `!=`, `<`, `>`, `<=`, `>=` and `~` (the title contains the value). `*` as a value means any,
so `blocked_on=*` is a card that waits on something and `not blocked_on=*` one that does not. An age
is a number and a unit, `30m`, `12h` or `2d`. Predicates combine with `and`, `or`, `not` and
parentheses; `not` binds tightest, then `and`, then `or`. A value with spaces is quoted.

The expression is parsed once into a postfix list of strings and run against each row, so the same
language serves every mode that lists cards. Plain lists and strings only: the Codon census holds
this module.
"""

FIELDS = ("status", "age", "flag", "repo", "blocked_on", "title")
OPERATORS = ("=", "!=", "<", ">", "<=", ">=", "~")
SYMBOLS = "=!<>~"
SPLIT = "\x00"
SECONDS = {"m": 60, "h": 3600, "d": 86400}


def _tokens(text: str) -> list[str]:
    """Cut an expression into words, operators and parentheses.

    Returns:
        The tokens in order; a quoted value is one token with its quotes removed.

    Raises:
        ValueError: When a quote is never closed.

    """
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            end = text.find('"', i + 1)
            if end < 0:
                message = "an unclosed quote in the filter"
                raise ValueError(message)
            out.append(text[i + 1 : end])
            i = end + 1
        elif ch in "()":
            out.append(ch)
            i += 1
        elif ch.isspace():
            i += 1
        else:
            # a run of operator characters, or a run of anything else up to a break
            symbol, j = ch in SYMBOLS, i + 1
            while (
                j < len(text)
                and text[j] not in '() "'
                and (text[j] in SYMBOLS) == symbol
            ):
                j += 1
            out.append(text[i:j])
            i = j
    return out


def _peek(tokens: list[str], pos: list[int]) -> str:
    """Look at the next token.

    Returns:
        The token, or an empty string at the end.

    """
    return tokens[pos[0]] if pos[0] < len(tokens) else ""


def _take(tokens: list[str], pos: list[int], what: str) -> str:
    """Consume the next token.

    Returns:
        The token.

    Raises:
        ValueError: When the expression ends where `what` was expected.

    """
    if pos[0] >= len(tokens):
        message = f"the filter ends where {what} was expected"
        raise ValueError(message)
    pos[0] += 1
    return tokens[pos[0] - 1]


def _predicate(tokens: list[str], pos: list[int], out: list[str]) -> None:
    """Parse `field op value` and emit it.

    Raises:
        ValueError: When the field or operator is not one the language has.

    """
    field = _take(tokens, pos, "a field")
    op = _take(tokens, pos, f"an operator after {field}")
    value = _take(tokens, pos, f"a value after {field}{op}")
    if field not in FIELDS:
        message = f"{field} is not a field; the fields are {', '.join(FIELDS)}"
        raise ValueError(message)
    if op not in OPERATORS:
        message = f"{op} is not an operator; the operators are {' '.join(OPERATORS)}"
        raise ValueError(message)
    out.append(field + SPLIT + op + SPLIT + value)


def _atom(tokens: list[str], pos: list[int], out: list[str]) -> None:
    """Parse a parenthesised expression or a predicate.

    Raises:
        ValueError: When a parenthesis is never closed.

    """
    if _peek(tokens, pos) == "(":
        pos[0] += 1
        _or(tokens, pos, out)
        if _take(tokens, pos, "a closing parenthesis") != ")":
            message = "a parenthesis in the filter is not closed"
            raise ValueError(message)
    else:
        _predicate(tokens, pos, out)


def _not(tokens: list[str], pos: list[int], out: list[str]) -> None:
    """Parse `not` and what it negates."""
    if _peek(tokens, pos) == "not":
        pos[0] += 1
        _not(tokens, pos, out)
        out.append("NOT")
    else:
        _atom(tokens, pos, out)


def _and(tokens: list[str], pos: list[int], out: list[str]) -> None:
    """Parse terms joined by `and`."""
    _not(tokens, pos, out)
    while _peek(tokens, pos) == "and":
        pos[0] += 1
        _not(tokens, pos, out)
        out.append("AND")


def _or(tokens: list[str], pos: list[int], out: list[str]) -> None:
    """Parse terms joined by `or`."""
    _and(tokens, pos, out)
    while _peek(tokens, pos) == "or":
        pos[0] += 1
        _and(tokens, pos, out)
        out.append("OR")


def parse(text: str) -> list[str]:
    """Parse a filter into postfix.

    Args:
        text: The expression, e.g. `status=ready and not blocked_on=*`.

    Returns:
        The postfix list: a predicate is `field`, `op` and `value` joined by NUL; the combinators
        are `AND`, `OR` and `NOT`. An empty expression is an empty list, which keeps every row.

    Raises:
        ValueError: When the expression is not well formed, naming what is wrong.

    """
    tokens = _tokens(text)
    if not tokens:
        return []
    out: list[str] = []
    pos = [0]
    _or(tokens, pos, out)
    if pos[0] < len(tokens):
        message = f"unexpected {tokens[pos[0]]} in the filter"
        raise ValueError(message)
    return out


def _seconds(value: str) -> float:
    """Read an age such as 30m, 12h or 2d.

    Returns:
        The seconds.

    Raises:
        ValueError: When it is not a number and a unit.

    """
    unit = value[-1:]
    number = value[:-1]
    if unit not in SECONDS or not number.replace(".", "", 1).isdigit():
        message = (
            f"{value} is not an age; write a number and a unit, such as 30m, 12h or 2d"
        )
        raise ValueError(message)
    return float(number) * SECONDS[unit]


def _compare(left: float, op: str, right: float) -> bool:
    """Compare two numbers by an operator.

    Returns:
        Whether the relation holds.

    """
    if op == "=":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    return left >= right


def _holds(field: str, op: str, value: str, row: dict[str, str]) -> bool:
    """Judge one predicate against a row.

    Args:
        field: One of FIELDS.
        op: One of OPERATORS.
        value: What the field is compared with.
        row: The card's row: cite, age_days, status, flag, blocked_on and title, as text.

    Returns:
        Whether the predicate holds.

    Raises:
        ValueError: When an age is compared with `~` or a text field with `<`, `>`, `<=` or `>=`,
            or the age is not a number and a unit.

    """
    if field == "age":
        if op == "~":
            message = "age cannot be compared with ~"
            raise ValueError(message)
        return _compare(
            float(row.get("age_days", "0")) * SECONDS["d"], op, _seconds(value)
        )
    have = (
        row.get("cite", "").partition(":")[0] if field == "repo" else row.get(field, "")
    )
    if op == "~":
        return value.lower() in have.lower()
    if op in {"=", "!="}:
        same = bool(have) if value == "*" else have.lower() == value.lower()
        return same if op == "=" else not same
    message = f"{op} compares numbers; {field} is text, so use = != or ~"
    raise ValueError(message)


def matches(postfix: list[str], row: dict[str, str]) -> bool:
    """Run a parsed filter against a card's row.

    Args:
        postfix: The list parse returned.
        row: The card's row.

    Returns:
        Whether the row is kept; true for an empty filter. A predicate that cannot be judged (an age
        that is not a number and a unit, `<` on a text field) raises ValueError from _holds.

    """
    stack: list[bool] = []
    for item in postfix:
        if item == "NOT":
            stack.append(not stack.pop())
        elif item in {"AND", "OR"}:
            right, left = stack.pop(), stack.pop()
            stack.append(left and right if item == "AND" else left or right)
        else:
            field, op, value = item.split(SPLIT)
            stack.append(_holds(field, op, value, row))
    return all(stack)
