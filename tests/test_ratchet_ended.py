# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1654: a series is judged ended against the repo's newest GATE-TIME sample only."""

import json

from nemik.ratchetseries import ended_series, export_series

BATCH = 1_000_000  # ms: one gate run sends every series together
LATER_BATCH = 9_000_000  # ms: a later gate run
LONE_LANDED = 50_000_000  # ms: much later, one ratchet's landed sample
NONE: dict[str, str] = {}


def _line(
    ratchet: str, value: int, at: int, stage: str = "", labels: dict[str, str] = NONE
) -> str:
    """Write one export line for repo `r`: one ratchet, one sample.

    Returns:
        The line, newline-terminated.

    """
    metric = {"repo": "r", "ratchet": ratchet} | labels
    if stage:
        metric["stage"] = stage
    row = {"metric": metric, "values": [value], "timestamps": [at]}
    return json.dumps(row) + "\n"


def test_a_lone_landed_sample_does_not_make_the_others_read_ended() -> None:
    """The 14:37Z case: A and B in one gate batch, then only A has a much later landed sample."""
    text = (
        _line("a.json", 5, BATCH)
        + _line("b.json", 7, BATCH)
        + _line("a.json", 4, LONE_LANDED, stage="landed")
    )
    assert ended_series(text) == []


def test_a_series_missing_from_a_later_gate_batch_has_ended() -> None:
    """A real ending: both in the first batch, only A in the next gate batch."""
    text = (
        _line("a.json", 5, BATCH)
        + _line("b.json", 7, BATCH)
        + _line("a.json", 4, LATER_BATCH)
    )
    assert ended_series(text) == [("r", "b.json")]


def test_a_repo_with_only_landed_samples_is_not_judged() -> None:
    """Nothing says when a gate batch happened, so nothing is ended."""
    text = _line("a.json", 5, BATCH, stage="landed") + _line(
        "b.json", 7, LONE_LANDED, stage="landed"
    )
    assert ended_series(text) == []


def test_the_guessed_pair_is_still_one_series() -> None:
    """guessed=true then guessed=false of one ratchet read as one, not as an ended one."""
    text = _line("a.json", 5, BATCH, labels={"guessed": "true"}) + _line(
        "a.json", 4, LATER_BATCH, labels={"guessed": "false"}
    )
    assert ended_series(text) == []
    assert export_series(text) == [("r", "a.json", [5, 4])]


def test_the_values_still_merge_both_stages() -> None:
    """Judging ends by gate time leaves the value history alone: both stages' samples are there."""
    text = _line("a.json", 5, BATCH) + _line("a.json", 4, LONE_LANDED, stage="landed")
    assert export_series(text) == [("r", "a.json", [5, 4])]
