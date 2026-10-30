# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W366: cards as issue-tracker issues (GitHub / Forgejo shape), a read-only mirror.

A serializer over nemik.projection (W413). Each Task becomes an issue: its title, a body that
names the cite (so a mirrored issue always leads back to the card), `state` open or closed, the
repo as a label, and `blocked_by`, the cites of its predecessors. GitHub's issue-dependency
endpoints and Forgejo's dependency endpoints both take "this issue is blocked by that one"
(docs/integration-survey.md), so the mirror's writer resolves each blocked_by cite to the issue
it created; that writer is a connector (W371), not this module. Nothing here writes anywhere:
`nemik-export --format issues` prints JSON.

Jira's CSV import documents only parent/child columns, not issue links (the survey's verified
finding), so a Jira mirror would lose the blocking edges; it is left to the connector rather
than a lossy file.

nemik:W958: given a tracker's recorded issues, `plan_text` prints the calls a mirror would make
(nemik.mirror.plan), reading them with nemik.tracker; it sends nothing.
"""

from __future__ import annotations

import json

from nemik.mirror import plan
from nemik.projection import Link, Task
from nemik.tracker import read_issues, row_of


def to_issues(tasks: list[Task]) -> list[dict[str, object]]:
    """One issue per task, in cite order.

    Returns:
        The issue rows, one per task: cite, title, body, state, labels and blocked_by.

    """
    return [
        {
            "cite": t.cite,
            "title": t.name,
            "body": f"nemik card {t.cite}",
            "state": "closed" if t.done else "open",
            "labels": [t.repo],
            "blocked_by": [link.cite for link in t.preds],
        }
        for t in tasks
    ]


def write(tasks: list[Task]) -> str:
    """Render the cards as issues.

    Returns:
        The issues as indented JSON.

    """
    return json.dumps(to_issues(tasks), indent=1)


def plan_text(tasks: list[Task], tracker_text: str) -> str:
    """Print the calls that would bring a tracker's recorded issues in line with the cards.

    Args:
        tasks: The cards to mirror.
        tracker_text: The JSON array a GitHub or Forgejo issues endpoint answered.

    Returns:
        One line per call (action, cite, the fields it changes), a line per pull request skipped,
        and a total. Issues the tracker holds that nemik did not mirror are left alone.

    """
    found = read_issues(tracker_text)
    rows = [row_of(issue) for issue in found if not issue.is_pull_request]
    calls = plan(to_issues(tasks), rows)
    lines = [
        f"{action} {cite} {','.join(sorted(fields))}".rstrip()
        for action, cite, fields in calls
    ]
    lines += [f"skipped pull request #{i.number}" for i in found if i.is_pull_request]
    lines.append(f"{len(calls)} call(s) against {len(rows)} issue(s) of the tracker")
    return "\n".join(lines) + "\n"


def read(text: str) -> list[Task]:
    """Read the tasks an issues document written by `write` holds (for the round-trip test).

    Returns:
        The tasks, numbered from 1, each with its blocked-by links.

    """
    rows = json.loads(text)
    return [
        Task(
            uid=i,
            cite=str(r["cite"]),
            name=str(r["title"]),
            done=r["state"] == "closed",
            preds=tuple(
                Link(c, c.partition(":")[0] != str(r["cite"]).partition(":")[0])
                for c in r["blocked_by"]
            ),
        )
        for i, r in enumerate(rows, start=1)
    ]
