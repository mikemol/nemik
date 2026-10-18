# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W369: the mirror plan creates, updates, closes and reopens by cite, and is idempotent."""

from nemik.mirror import plan


def _issue(cite: str, state: str = "open", title: str = "t") -> dict[str, object]:
    labels: list[object] = ["alpha"]
    blocked: list[object] = []
    return {
        "cite": cite,
        "title": title,
        "body": f"nemik card {cite}",
        "state": state,
        "labels": labels,
        "blocked_by": blocked,
    }


def test_a_card_the_tracker_lacks_is_created_whole() -> None:
    """The create call carries the whole wanted issue."""
    want = _issue("alpha:W1")
    assert plan([want], []) == [("create", "alpha:W1", want)]


def test_the_tracker_in_agreement_needs_no_calls() -> None:
    """Idempotent: planning against what was just made returns nothing."""
    issues = [_issue("alpha:W1"), _issue("alpha:W2", state="closed")]
    assert plan(issues, issues) == []


def test_a_retitled_card_is_an_update_of_that_field_only() -> None:
    """Only the field that differs is sent."""
    got = plan([_issue("alpha:W1", title="new")], [_issue("alpha:W1")])
    assert got == [("update", "alpha:W1", {"title": "new"})]


def test_state_changes_are_close_and_reopen() -> None:
    """A done card closes its open issue; a reopened card reopens its closed one."""
    closing = plan([_issue("alpha:W1", state="closed")], [_issue("alpha:W1")])
    reopening = plan([_issue("alpha:W1")], [_issue("alpha:W1", state="closed")])
    assert closing == [("close", "alpha:W1", {})]
    assert reopening == [("reopen", "alpha:W1", {})]


def test_reordered_labels_are_no_change_and_foreign_issues_are_left_alone() -> None:
    """Lists compare as sets; a tracker issue with no wanted card is never deleted."""
    held = _issue("alpha:W1")
    held["labels"] = ["beta", "alpha"]
    want = _issue("alpha:W1")
    want["labels"] = ["alpha", "beta"]
    assert plan([want], [held, _issue("someone:W9")]) == []
