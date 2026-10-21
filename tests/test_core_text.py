# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W829: the page's small text and colour functions over plain data."""

from nemik.core.text import repo_hue

DEGREES = 360
CODE_OF_A = 97
HUE_OF_AB = 225


def test_the_hue_of_nothing_is_zero() -> None:
    """An empty name hashes to 0."""
    assert repo_hue("") == 0


def test_the_hue_is_a_rolling_hash_of_the_characters_modulo_360() -> None:
    """'a' is 97; 'ab' is (97 * 31 + 98) % 360 = 225."""
    assert repo_hue("a") == CODE_OF_A
    assert repo_hue("ab") == HUE_OF_AB


def test_the_hue_stays_a_degree() -> None:
    """Whatever the name, the hue is in [0, 360)."""
    for name in ("nemik", "mtools", "luthen-observability", "gabion", "x" * 500):
        assert 0 <= repo_hue(name) < DEGREES
