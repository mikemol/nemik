# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2110: //:pre_gate names the tests that a hand-picked pre-gate run kept leaving out.

Each member was named by a gate refusal (nemik:R495): the ratchets and registries that failed a
stack the session's own targets passed. The suite is a subset of //:precommit; this holds that the
suite block in BUILD.bazel lists exactly them. A member that is not a test target fails bazel's own
load of the suite, so that is not re-checked here.
"""

from pathlib import Path

MEMBERS = [
    "test_architecture",
    "test_codon_census",
    "test_codon_wall_incidence",
    "test_codon_wall_table",
    "test_mypy_ratchet",
    "test_nemik_src",
    "test_precommit_gate",
    "test_precommit_nemik_src",
    "test_ruff_ratchet",
    "test_skill",
]
ROOT = Path(__file__).parents[1]


def _listed() -> list[str]:
    text = (ROOT / "BUILD.bazel").read_text(encoding="utf-8")
    start = text.index('name = "pre_gate"')
    block = text[start : text.index("]", start)]
    names = [line.strip().strip('",').removeprefix(":") for line in block.splitlines()]
    return sorted(name for name in names if name.startswith("test_"))


def test_the_suite_lists_exactly_the_members() -> None:
    """MUTANT: a member dropped from the suite, or one added, is the hand-picked list again."""
    assert _listed() == sorted(MEMBERS)


def test_the_members_are_the_ones_the_refusals_named() -> None:
    """The ratchets, registries and Codon wall tests that failed stacks the session passed."""
    assert {"test_ruff_ratchet", "test_mypy_ratchet", "test_codon_wall_incidence"} <= set(
        _listed()
    )
    assert {"test_architecture", "test_skill", "test_precommit_gate"} <= set(_listed())
