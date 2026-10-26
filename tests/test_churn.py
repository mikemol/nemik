# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W495: a poll's change is classified by what the drawn graph must do to follow it."""

from datetime import UTC, datetime, timedelta

from nemik.churn import churn, classify, commit_classes

T0 = datetime(2026, 10, 1, tzinfo=UTC)


def _card(symbol: str, status: str = "ready", title: str = "t", **more: object) -> dict:
    return {"symbol": symbol, "title": title, "status": status, **more}


def _queue(*cards: dict, heartbeat: str = "a") -> dict:
    return {"waypoints": list(cards), "residue": [], "heartbeat": heartbeat}


def test_each_kind_of_change_is_classified() -> None:
    """A heartbeat change, an attribute change, a status flip and a structure change each class."""
    base = _queue(_card("W1"))
    assert classify(base, _queue(_card("W1"), heartbeat="b")) == "identical"
    assert classify(base, _queue(_card("W1", title="new"))) == "attribute"
    assert classify(base, _queue(_card("W1", "working"))) == "state"
    assert classify(base, _queue(_card("W1"), _card("W2"))) == "structural"
    assert classify(base, _queue(_card("W1", "done"))) == "structural"
    assert classify(base, _queue(_card("W1", enables=["W2"]))) == "structural"


def test_a_poll_takes_the_worst_class_among_the_repos_that_moved() -> None:
    """A poll over several repos is classed by the gravest change any of them made."""
    quiet = [(T0, _queue(_card("W1")))]
    busy = [
        (T0, _queue(_card("W1"))),
        (T0 + timedelta(seconds=90), _queue(_card("W1", title="x"))),
        (T0 + timedelta(seconds=150), _queue(_card("W1", title="x"), _card("W2"))),
    ]
    end = T0 + timedelta(seconds=240)
    result = churn({"quiet": quiet, "busy": busy}, T0, end, 60)
    # polls: [0,60) identical, [60,120) attribute, [120,180) structural, [180,240) identical
    assert result.polls == 4
    assert result.counts == {"identical": 2, "attribute": 1, "structural": 1}
    assert result.redraws_now() == 0.5
    assert result.redraws_patching_attributes() == 0.25


def test_commits_are_counted_by_what_each_did() -> None:
    """Each commit is counted under the class of change it made."""
    snaps = [
        (T0, _queue(_card("W1"))),
        (T0 + timedelta(seconds=10), _queue(_card("W1", "working"))),
        (T0 + timedelta(seconds=20), _queue(_card("W1", "working"), _card("W2"))),
    ]
    found = commit_classes({"r": snaps}, T0, T0 + timedelta(minutes=1))
    assert found == {"state": 1, "structural": 1}
