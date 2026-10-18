# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W370: an issue-tracker event as printed lines, never a queue write.

A GitHub or Forgejo webhook (or a poll) delivers an issues or issue_comment event as JSON. `lines`
reads one and returns text for a person or a loop to act on: the command that would mint a card
for a newly opened issue, a suggested status change for a card nemik mirrored (nemik.mirror stamps
the issue body `nemik card <repo>:W<n>`), or the body of a letter for the owning repo's inbox when
someone comments. Nothing here writes a queue or touches the network; the webhook or poll that
delivers events needs each tool's token later (operator: act). The module imports only json, so
the Codon census compiles it.
"""

import json

WRITER = "mikemol-paths-forward --state .claude/paths-forward.json"
MARKER = "nemik card "
TITLE_LIMIT = 150


def field(doc: object, path: list[str]) -> str:
    """Read one value from nested JSON.

    Args:
        doc: Parsed JSON.
        path: The keys to follow.

    Returns:
        The value as text when it is a string or a number, otherwise an empty string.

    """
    cur = doc
    for key in path:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    if isinstance(cur, (str, int)):
        return str(cur)
    return ""


def quote(text: str) -> str:
    """Quote text for a shell command line.

    Args:
        text: Any text.

    Returns:
        The text in single quotes, with each embedded single quote closed, escaped and reopened.

    """
    return "'" + text.replace("'", "'\\''") + "'"


def title_of(text: str) -> str:
    """Make an issue title fit the writer's rule for a card title.

    Args:
        text: The issue's title.

    Returns:
        One line of at most 150 characters without `;`, which the writer refuses.

    """
    one = " ".join(text.replace(";", ",").split())
    return one[:TITLE_LIMIT]


def mirrored_cite(body: str) -> str:
    """Find the card a mirrored issue stands for.

    Args:
        body: The issue's body.

    Returns:
        The `<repo>:W<n>` after `nemik card `, or an empty string for an issue nemik did not write.

    """
    at = body.find(MARKER)
    if at < 0:
        return ""
    words = body[at + len(MARKER) :].split()
    return words[0] if words else ""


def lines(payload: str) -> list[str]:
    """Turn one issue event into the lines a person or a loop would act on.

    Args:
        payload: The event's JSON text.

    Returns:
        Comment lines naming the issue, then what to do: a card to mint (opened), a status to
        suggest for a mirrored card (closed, reopened), or a letter body (a comment created).
        Empty when the text is not JSON or the event is one nemik does not read.

    """
    try:
        doc: object = json.loads(payload)
    except ValueError:
        return []
    action = field(doc, ["action"])
    repo = field(doc, ["repository", "full_name"])
    number = field(doc, ["issue", "number"])
    if not (action and repo and number):
        return []
    ref = f"{repo}#{number}"
    title = title_of(field(doc, ["issue", "title"]))
    cite = mirrored_cite(field(doc, ["issue", "body"]))
    head = f"# {ref} {action}: {field(doc, ['issue', 'html_url'])}"
    if action == "opened" and not cite:
        return [head, f"{WRITER} --add {quote(title)}"]
    if action in {"closed", "reopened"} and cite:
        status = "done" if action == "closed" else "ready"
        change = f"{WRITER} --update {cite.partition(':')[2]} --status {status}"
        return [head, f"# suggest, if {cite} is this repo's card: {change}"]
    comment = field(doc, ["comment", "body"])
    if action == "created" and comment:
        who = field(doc, ["comment", "user", "login"]) or "someone"
        return [
            head,
            f"# letter for the inbox of the repo that owns {cite or ref}:",
            f"{who} commented on {ref}:",
            comment,
        ]
    return []
