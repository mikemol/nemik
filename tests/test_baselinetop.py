# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W980: a ratchet baseline is totalled by rule and by file, heaviest first."""

import pytest

from nemik.baselinetop import by_file, by_rule

BASELINE = (
    '{"a.py": {"D103": 3, "E501": 1}, "b.py": {"D103": 2, "T201": 4},'
    ' "c.py": {"E501": 1}}'
)


def test_the_totals_by_rule_are_heaviest_first_with_ties_by_name() -> None:
    """D103 is 5, T201 4, E501 2."""
    assert by_rule(BASELINE) == [("D103", 5), ("T201", 4), ("E501", 2)]


def test_the_totals_by_file_are_heaviest_first() -> None:
    """b.py holds 6, a.py 4, c.py 1."""
    assert by_file(BASELINE) == [("b.py", 6), ("a.py", 4), ("c.py", 1)]


def test_a_baseline_of_the_wrong_shape_is_refused() -> None:
    """Counts must be integers inside an object per file."""
    with pytest.raises(TypeError, match="not a count"):
        by_rule('{"a.py": {"D103": "three"}}')
    with pytest.raises(TypeError, match="not an object of rules"):
        by_rule('{"a.py": 3}')
