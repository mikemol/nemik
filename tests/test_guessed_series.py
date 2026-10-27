# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1038: a ratchet's guessed=true and guessed=false series are one ratchet, not two."""

from nemik.ratchetseries import ended_series, export_series

OLD = (
    '{"metric":{"repo":"r","ratchet":"x.json","guessed":"true"},'
    '"values":[9,8,7],"timestamps":[1000,2000,3000]}\n'
)
NEW = (
    '{"metric":{"repo":"r","ratchet":"x.json","guessed":"false"},'
    '"values":[7,6],"timestamps":[3000,4000]}\n'
)
OTHER = (
    '{"metric":{"repo":"r","ratchet":"y.json"},'
    '"values":[1,1,1,1],"timestamps":[1000,2000,3000,4000]}\n'
)
SLACK_MS = 60_000


def test_the_two_series_of_one_ratchet_are_one_value_list() -> None:
    """The guessed run ends where the declared run begins; read together they are one history."""
    rows = export_series(OLD + NEW)
    assert rows == [("r", "x.json", [9, 8, 7, 6])]


def test_a_ratchet_that_changed_label_has_not_ended() -> None:
    """Kept apart, the older series looked ended and the whole repo read unknown."""
    assert ended_series(OLD + NEW + OTHER) == []


def test_the_declared_sample_wins_where_both_stamp_the_same_instant() -> None:
    """At 3000 the guessed series says 7 and so does the declared one; make them differ."""
    older = OLD.replace("[9,8,7]", "[9,8,70]")
    assert export_series(older + NEW)[0][2] == [9, 8, 7, 6]
    assert export_series(NEW + older)[0][2] == [9, 8, 7, 6]
