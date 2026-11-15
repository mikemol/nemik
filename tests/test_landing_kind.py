# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1083: tools/landing_kind.py names a landing `image` or `ref` from its paths.

The fixtures are the eight landings of the stretch the reviewer read (nemik:R495): five touched
src and ship, three touched only tests, a doc and BUILD.bazel and do not.
"""

from landing_kind import kind, main, ships

LANDINGS = {
    "W1099": ["src/nemik/adapter.py", "src/nemik/blocks.py", "tests/test_blocks_activity.py"],
    "W1100": ["src/nemik/metrics.py", "checks/claims.py", "tests/test_metrics_activity.py"],
    "W1101": ["src/nemik/history.py", "tests/test_toil.py"],
    "W1102": ["src/nemik/adapter.py", "src/nemik/idle.py", "tests/test_idle_activity.py"],
    "W1083": ["src/nemik/history.py", "src/nemik/metrics.py", "tests/test_landed_candidates.py"],
    "W1093": ["tests/test_blocked_on_done.py"],
    "W1096": ["docs/builder-memory.md"],
    "W2052": ["BUILD.bazel", "tests/test_schemagen.py", "tests/test_codon_calls.py"],
}
SHIPPING = {"W1099", "W1100", "W1101", "W1102", "W1083"}
OK, USAGE = 0, 2


def test_the_five_src_landings_are_images_and_the_other_three_are_refs() -> None:
    """The kind follows the paths: src ships, tests, docs and BUILD do not."""
    got = {card: kind(paths) for card, paths in LANDINGS.items()}
    assert {c for c, k in got.items() if k == "image"} == SHIPPING
    assert {c for c, k in got.items() if k == "ref"} == set(LANDINGS) - SHIPPING


def test_a_pin_the_containerfile_and_a_manifest_ship() -> None:
    """The dependency pins, the Containerfile and the deploy manifest reach the image."""
    assert all(ships(p) for p in ("pyproject.toml", "uv.lock", "Containerfile", "deploy/x.yaml"))


def test_a_queue_file_and_a_tool_do_not() -> None:
    """MUTANT: treating every changed path as shipping would make the three ref landings images."""
    assert not any(ships(p) for p in (".claude/paths-forward.json", "tools/x.py", "docs/a.md"))


def test_main_succeeds_on_a_path_and_refuses_none() -> None:
    """The CLI answers a landing's paths, and a call with no path is a usage error."""
    assert main(["src/nemik/idle.py"]) == OK
    assert main([]) == USAGE
