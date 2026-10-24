# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""pollevents: what a poll of a tracker's issues asks of the queue, as printed lines (nemik:W370).

nemik.events reads a webhook's event (an `issues` payload with an action). A poll has no action: it
lists the tracker's issues as they stand, the shape recorded in tests/fixtures/trackers. So the
action is read from the state. An open issue nemik did not mirror is one to mint a card for; a
closed issue that does stand for a card (its body says `nemik card <repo>:W<n>`) suggests that card
is done; an open mirrored issue, a closed foreign one, and a pull request ask nothing. The lines are
the same kind nemik.events prints, for a person or a loop to act on, and nothing is written.

A poll sees the same issue every time it runs, so these lines repeat; recording which were acted on
belongs to the delivery (the ledger), not here.
"""

from nemik.events import WRITER, quote, title_of
from nemik.tracker import Issue, cite_of


def poll_lines(issues: list[Issue], repo: str) -> list[str]:
    """Turn a poll's issues into the lines a person or a loop would act on.

    Args:
        issues: The tracker's issues, as nemik.tracker read them.
        repo: The tracker repository, `OWNER/REPO`, for the references in the lines.

    Returns:
        For each issue that asks something, a comment line naming it and then the command to mint
        a card (an open issue nemik did not mirror) or a suggested status change (a closed
        mirrored issue); nothing for the rest.

    """
    out: list[str] = []
    for issue in issues:
        if issue.is_pull_request:
            continue
        cite = cite_of(issue.body)
        head = f"# {repo}#{issue.number} {issue.state}: {issue.url}"
        if not cite and issue.state == "open":
            out += [head, f"{WRITER} --add {quote(title_of(issue.title))}"]
        elif cite and issue.state == "closed":
            change = f"{WRITER} --update {cite.partition(':')[2]} --status done"
            out += [head, f"# suggest, if {cite} is this repo's card: {change}"]
    return out
