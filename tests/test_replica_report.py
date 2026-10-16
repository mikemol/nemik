# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W592: the replay result line becomes a verdict a tick can act on."""

from nemik.replica import parse, verdict

HEAD = "a" * 40
OLD = "b" * 40


def test_a_result_line_parses_and_a_malformed_one_has_no_sha() -> None:
    """Three fields, the last two numeric; anything else is no replay (an empty sha)."""
    replay = parse(f"{HEAD} 0 942\n")
    assert (replay.sha, replay.status, replay.seconds) == (HEAD, 0, 942)
    assert not parse("").sha
    assert not parse(f"{HEAD} x 9").sha
    assert not parse(f"{HEAD} 0").sha


def test_the_verdict_names_green_red_stale_and_none() -> None:
    """GREEN for exit 0 on the pushed sha, RED for any other exit, STALE for an older sha."""
    assert verdict(parse(f"{HEAD} 0 942"), HEAD).startswith("GREEN aaaaaaa")
    red = verdict(parse(f"{HEAD} 1 600"), HEAD)
    assert red.startswith("RED aaaaaaa")
    assert "--gate-red" in red
    assert verdict(parse(f"{OLD} 0 5"), HEAD).startswith("STALE")
    assert verdict(parse(""), HEAD).startswith("NONE")
