# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W369: the calls a one-way, idempotent mirror of cards to an issue tracker would make.

`plan` compares the issues nemik wants (nemik.issues.to_issues: cite, title, body, state, labels,
blocked_by) with the issues the tracker already holds, matched by cite, and returns the create,
update, close and reopen calls that would make the tracker agree. It touches no network and holds no
credential: it is the dry run, and the API client for each tool (a scoped token, an operator act)
reads the same calls later.

The mirror is one-way and never deletes. A tracker issue whose cite is not among the wanted cards is
somebody else's and is left alone. Running the plan against a tracker it has just brought into
agreement returns no calls. The module imports nothing, so the Codon census compiles it.
"""

CREATE, UPDATE, CLOSE, REOPEN = "create", "update", "close", "reopen"
FIELDS = ("title", "body", "labels", "blocked_by")
Call = tuple[str, str, dict[str, object]]


def by_cite(issues: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """Index issues by the cite that names the card they mirror.

    Args:
        issues: Issue rows, each with a `cite`.

    Returns:
        The rows keyed by cite; a row without one is left out.

    """
    return {str(row["cite"]): row for row in issues if row.get("cite")}


def same(wanted: object, held: object) -> bool:
    """Say whether two field values agree.

    Args:
        wanted: The value nemik wants.
        held: The value the tracker holds.

    Returns:
        True when equal; two lists agree when they hold the same entries in any order.

    """
    if isinstance(wanted, list) and isinstance(held, list):
        return sorted(str(entry) for entry in wanted) == sorted(
            str(entry) for entry in held
        )
    return wanted == held


def changes(want: dict[str, object], have: dict[str, object]) -> dict[str, object]:
    """Find the fields of an issue that differ from what is wanted.

    Args:
        want: The issue nemik wants.
        have: The issue the tracker holds.

    Returns:
        The wanted value of each of title, body, labels and blocked_by that the tracker's differs
        from; empty when they agree. Lists compare as sets, so a reordered label is no change.

    """
    return {k: want.get(k) for k in FIELDS if not same(want.get(k), have.get(k))}


def plan(
    wanted: list[dict[str, object]], existing: list[dict[str, object]]
) -> list[Call]:
    """List the calls that bring a tracker in line with the cards.

    Args:
        wanted: The issues nemik wants, as nemik.issues.to_issues returns them.
        existing: The issues the tracker already holds, matched by cite.

    Returns:
        (action, cite, fields) calls in cite order: create with the whole issue; update with the
        fields that differ; close or reopen with no fields when only the state differs.

    """
    have = by_cite(existing)
    calls: list[Call] = []
    for cite, want in sorted(by_cite(wanted).items()):
        held = have.get(cite)
        if held is None:
            calls.append((CREATE, cite, want))
            continue
        diff = changes(want, held)
        if diff:
            calls.append((UPDATE, cite, diff))
        if want.get("state") != held.get("state"):
            calls.append((CLOSE if want.get("state") == "closed" else REOPEN, cite, {}))
    return calls
