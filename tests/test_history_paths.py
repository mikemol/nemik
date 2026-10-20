# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W769: an old card's critical path, and whether it needs a repo with no live session."""

from nemik.history import card_table, critical_path, with_paths


def _docs() -> dict[str, object]:
    """Build two repos: a:W1 waits on a:W2 and b:W5; a:W2 on the operator; b:W5 down to ready b:W7.

    Returns:
        The parsed queues, by repo.

    """
    return {
        "a": {
            "waypoints": [
                {"symbol": "W1", "status": "blocked", "blocked_on": ["W2", "b:W5"]},
                {
                    "symbol": "W2",
                    "status": "blocked",
                    "blocked_on": ["operator: decide x"],
                },
                {"symbol": "W3", "status": "done", "blocked_on": []},
            ]
        },
        "b": {
            "waypoints": [
                {"symbol": "W5", "status": "blocked", "blocked_on": ["W6"]},
                {"symbol": "W6", "status": "blocked", "blocked_on": ["W7"]},
                {"symbol": "W7", "status": "ready", "blocked_on": []},
            ]
        },
    }


def test_the_critical_path_is_the_longest_chain_down_to_a_leaf() -> None:
    """a:W1 has two ways down; b's (W5, W6, W7) is longer than the operator hold under W2."""
    cards = card_table(_docs())
    labels = [label for label, _ in critical_path("a:W1", cards)]
    assert labels == ["a:W1(blocked)", "b:W5(blocked)", "b:W6(blocked)", "b:W7(ready)"]


def test_a_landed_blocker_is_not_a_hop_and_a_cycle_ends_the_path() -> None:
    """Done W3 adds nothing; a card blocked on itself's partner ends at the cycle mark."""
    docs: dict[str, object] = {
        "a": {
            "waypoints": [
                {"symbol": "W1", "status": "blocked", "blocked_on": ["W3", "W2"]},
                {"symbol": "W2", "status": "blocked", "blocked_on": ["W1"]},
                {"symbol": "W3", "status": "done", "blocked_on": []},
            ]
        }
    }
    labels = [label for label, _ in critical_path("a:W1", card_table(docs))]
    assert labels == ["a:W1(blocked)", "a:W2(blocked)", "a:W1(cycle)"]


def test_a_path_is_offline_free_only_when_every_repo_it_crosses_has_a_session() -> None:
    """With only a live, b's path is not free; with both live it is; the operator needs none."""
    rows = [{"cite": "a:W1"}, {"cite": "a:W2"}]
    docs = _docs()
    only_a = {r["cite"]: r for r in with_paths(rows, docs, {"a"})}
    assert only_a["a:W1"]["reach"] == "crosses offline: b"
    assert only_a["a:W2"]["reach"] == "OFFLINE-FREE"
    both = {r["cite"]: r for r in with_paths(rows, docs, {"a", "b"})}
    assert both["a:W1"]["reach"] == "OFFLINE-FREE"
