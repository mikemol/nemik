# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1848, W1849: the policy version nemik compares is the one the writer stamps on a mark."""

from mikemol.pathsforward.marks import judged

from nemik.realize import policy_version

NOW = "2026-11-26T12:00:00Z"
ITEM: dict[str, object] = {"waypoint": {"symbol": "W1"}}
DIGEST_LENGTH = 64


def test_the_version_is_the_one_the_writer_stamps_on_a_mark() -> None:
    """A mark built by the writer's own `judged` carries exactly what nemik compares against."""
    mark = judged("add", NOW, ITEM, {})
    assert mark["policy_version"] == policy_version()
    assert len(policy_version()) == DIGEST_LENGTH
