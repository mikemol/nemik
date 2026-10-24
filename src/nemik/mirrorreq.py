# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""mirrorreq: the HTTP requests a mirror plan comes to, for GitHub and Forgejo (nemik:W959, W369).

nemik.mirror.plan says what a tracker needs (create, update, close, reopen); this says what to send.
Each call becomes one request, a method, a path and a JSON body, and nothing here opens a socket or
holds a credential: sending is a separate step that needs each tool's scoped token, which is the
operator's to give (nemik:W959). So the requests can be printed, read and tested before any token
exists.

Two dialects, from the documented REST APIs and the issues recorded in tests/fixtures/trackers:
GitHub is rooted at /repos/OWNER/REPO/issues; Forgejo (Gitea's API) at
/api/v1/repos/OWNER/REPO/issues. Both create with POST and change with PATCH of the issue's
number. Where they differ:
- Forgejo's create takes label ids, not names, and nemik knows names, so a Forgejo request
  carries no labels (a label needs its id looked up, a later step); GitHub's takes names.
- Neither create body here sets a closed state: a done card is created open and the next plan,
  finding it open when it should be closed, adds the close. The mirror is idempotent, so it
  settles.
- blocked_by is never in a body: the dependency edges are separate endpoints, a step of their own.
"""

from typing import NamedTuple

from nemik.mirror import CLOSE, CREATE, REOPEN, UPDATE, Call
from nemik.tracker import Issue, cite_of

GITHUB, FORGEJO = "github", "forgejo"
ROOTS = {GITHUB: "", FORGEJO: "/api/v1"}
BODY_FIELDS = ("title", "body", "labels")
STATES = {CLOSE: "closed", REOPEN: "open"}


class Request(NamedTuple):
    """One HTTP request to a tracker's issue API."""

    method: str
    path: str
    body: dict[str, object]


def numbers(issues: list[Issue]) -> dict[str, int]:
    """Map each mirrored card to the number of the issue that stands for it.

    Args:
        issues: The tracker's issues, as nemik.tracker read them.

    Returns:
        cite -> issue number, for the issues whose body names a card and that are not pull requests.

    """
    return {
        cite_of(issue.body): issue.number
        for issue in issues
        if cite_of(issue.body) and not issue.is_pull_request
    }


def _fields(tool: str, fields: dict[str, object]) -> dict[str, object]:
    """Pick the body fields a tool accepts from a call's fields.

    Returns:
        title, body and, for GitHub only, labels, as far as the call has them.

    """
    kept = [k for k in BODY_FIELDS if k in fields and (k != "labels" or tool == GITHUB)]
    return {k: fields[k] for k in kept}


def requests_for(
    tool: str, slug: str, calls: list[Call], issue_numbers: dict[str, int]
) -> list[Request]:
    """Turn a plan's calls into the requests that carry them out.

    Args:
        tool: `github` or `forgejo`.
        slug: The tracker repository, `OWNER/REPO`.
        calls: nemik.mirror.plan's (action, cite, fields) calls.
        issue_numbers: cite -> issue number, from `numbers`; an update, close or reopen needs it.

    Returns:
        One request per call, in the plan's order. A call that changes only fields the tool does
        not take (labels on Forgejo) gives no request.

    Raises:
        ValueError: When the tool is unknown, or a call changes a card the tracker has no issue for.

    """
    if tool not in ROOTS:
        message = f"unknown tool {tool!r}: {GITHUB} or {FORGEJO}"
        raise ValueError(message)
    base = f"{ROOTS[tool]}/repos/{slug}/issues"
    out: list[Request] = []
    for action, cite, fields in calls:
        if action == CREATE:
            out.append(Request("POST", base, _fields(tool, fields)))
            continue
        if cite not in issue_numbers:
            message = f"no issue number for {cite}: the tracker has none to {action}"
            raise ValueError(message)
        body: dict[str, object] = (
            _fields(tool, fields) if action == UPDATE else {"state": STATES[action]}
        )
        if body:
            out.append(Request("PATCH", f"{base}/{issue_numbers[cite]}", body))
    return out
