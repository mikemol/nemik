# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1169: a repo's letters read from its issues, by the table of docs/inbox-as-issues.md.

A letter is an issue opened on the recipient's repo. Its sender is the label `from:<repo>`, its
kind the label `kind:<kind>` (ask, info, alert or reply), and the card it cites the label
`cites:<repo>:W<n>`. The issue list arrives as the JSON the issues endpoint answered, read by
nemik.tracker (W957): this module does not fetch anything, so a recorded answer is its fixture and
the transport (the gh subprocess of docs/courier-read-path.md, off by default) is a separate step.
A pull request is not a letter. An issue with no `kind:` label is not a letter either: the
label is what marks one.
"""

from nemik.tracker import Issue, read_issues

FROM = "from:"
KIND = "kind:"
CITES = "cites:"
OPEN = "open"


def _labelled(issue: Issue, prefix: str) -> list[str]:
    """Read the values of the labels that start with a prefix.

    Returns:
        Each such label's text after the prefix, in the issue's order.

    """
    return [name[len(prefix) :] for name in issue.labels if name.startswith(prefix)]


def letter_of(issue: Issue) -> dict[str, str]:
    """Read one issue as a letter.

    Args:
        issue: A tracker issue.

    Returns:
        url, title, state, from, kind and cites, each text; `from` and `cites` empty when the
        issue carries no such label, and the first label wins when it carries several. An empty
        dict when the issue is a pull request or has no `kind:` label.

    """
    kinds = _labelled(issue, KIND)
    if issue.is_pull_request or not kinds:
        return {}
    senders, cited = _labelled(issue, FROM), _labelled(issue, CITES)
    return {
        "url": issue.url,
        "title": issue.title,
        "state": issue.state,
        "from": senders[0] if senders else "",
        "kind": kinds[0],
        "cites": cited[0] if cited else "",
    }


def letters_of(text: str) -> list[dict[str, str]]:
    """Read a tracker's issue list as letters.

    Args:
        text: The JSON array the issues endpoint answered.

    Returns:
        The letters in the tracker's order, closed ones included; text that is not JSON raises
        ValueError and JSON of the wrong shape TypeError, as nemik.tracker does.

    """
    found = [letter_of(issue) for issue in read_issues(text)]
    return [letter for letter in found if letter]


def unclaimed(letters: list[dict[str, str]], queue_text: str) -> list[dict[str, str]]:
    """Name the open letters that no waypoint of the repo's queue cites.

    Args:
        letters: The letters, from letters_of.
        queue_text: The repo's queue as text; a letter is claimed when its URL or its `cites`
            label (when it has one) appears in it.

    Returns:
        The open letters not claimed, in order: nemik-inbound's UNCLAIMED rows.

    """
    return [
        letter
        for letter in letters
        if letter["state"] == OPEN
        and letter["url"] not in queue_text
        and not (letter["cites"] and letter["cites"] in queue_text)
    ]


def by_peer(letters: list[dict[str, str]]) -> list[str]:
    """Count the letters by sender alone, the grouping a per-peer census compares against.

    Args:
        letters: The letters, from letters_of.

    Returns:
        One line `<from> <n> letter(s) open=<n> closed=<n>` per sender, sorted; a sender the
        issue does not name reads `-`. The same letters as census, with the kinds summed.

    """
    counts: dict[str, list[int]] = {}
    for letter in letters:
        row = counts.setdefault(letter["from"] or "-", [0, 0])
        row[0 if letter["state"] == OPEN else 1] += 1
    return [
        f"{peer} {sum(counts[peer])} letter(s) open={counts[peer][0]} closed={counts[peer][1]}"
        for peer in sorted(counts)
    ]


def census(letters: list[dict[str, str]]) -> list[str]:
    """Count the letters by sender and kind, for comparing a sent census by value.

    Args:
        letters: The letters, from letters_of.

    Returns:
        One line `<from> <kind> open=<n> closed=<n>` per pair, sorted; a sender the issue does not
        name reads `-`.

    """
    counts: dict[str, list[int]] = {}
    for letter in letters:
        key = f"{letter['from'] or '-'} {letter['kind']}"
        row = counts.setdefault(key, [0, 0])
        row[0 if letter["state"] == OPEN else 1] += 1
    return [
        f"{key} open={counts[key][0]} closed={counts[key][1]}" for key in sorted(counts)
    ]
