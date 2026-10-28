# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W320: the workflow model (data/workflows.toml) corresponds to skills/nemik/SKILL.md and to the
code that enforces it. Each direction is checked, so a rule the skill teaches but the model lacks,
or a
model step the skill never mentions, fails here.
"""

from __future__ import annotations

import re
from importlib.resources import files
from pathlib import Path

from nemik.workflows import advice_only, load, transitions

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "skills/nemik/SKILL.md").read_text()
SHAPES = files("nemik.data").joinpath("shapes.ttl").read_text()
MODEL = load()


def test_every_transition_joins_declared_states() -> None:
    states = set(MODEL["lifecycle"]["states"])
    assert all({t["from"], t["to"]} <= states for t in transitions(MODEL))


def test_the_skill_teaches_every_lifecycle_command() -> None:
    taught = [t["command"] for t in transitions(MODEL) if t["command"] in SKILL]
    missing = [t["command"] for t in transitions(MODEL) if t["command"] not in taught]
    assert not missing, f"skills/nemik/SKILL.md never teaches {missing}"


def test_every_enforcer_the_model_names_exists() -> None:
    declared = [e for t in transitions(MODEL) for e in t["enforced_by"]]
    declared += [e for r in MODEL["rule"] for e in r["enforced_by"]]
    for e in declared:
        if "shape" in e:
            assert e["shape"] in SHAPES, f"no shape message holds {e['shape']!r}"
        elif (ROOT / e["hook"]).exists():  # the hook is not in a Bazel test sandbox
            assert e["text"] in (ROOT / e["hook"]).read_text()


def test_the_skill_numbers_exactly_the_rules_the_model_declares() -> None:
    rules = MODEL["rule"]
    section = SKILL.split("## The four rules that make the graph work")[1].split(
        "\n## "
    )[0]
    numbered = re.findall(r"^\d+\. \*\*(.+?)\*\*", section, flags=re.MULTILINE)
    assert len(numbered) == len(rules)
    for rule in rules:
        assert rule["skill_anchor"] in section, (
            f"rule {rule['id']} has no anchor in SKILL.md"
        )


def test_every_workflow_step_command_appears_in_the_skill() -> None:
    commands = [s["command"] for w in MODEL["workflow"] for s in w["steps"]]
    assert [c for c in commands if c not in SKILL] == []


def test_every_documented_command_has_a_workflow_or_is_reference() -> None:
    table = re.findall(r"^\| `(nemik-[a-z-]+)", SKILL, flags=re.MULTILINE)
    steps = {s["command"] for w in MODEL["workflow"] for s in w["steps"]}
    placed = steps | set(MODEL["reference"]["commands"])
    assert [c for c in table if c not in placed] == []
    # and the reference list names only commands the skill documents
    assert [c for c in MODEL["reference"]["commands"] if c not in table] == []


def test_what_is_taught_but_not_enforced_is_the_reviewed_set() -> None:
    """Adding an unenforced transition or rule changes this set on purpose, in a reviewed diff."""
    assert advice_only(MODEL) == [
        "working->done (--status done)",
        "ready->dropped (--drop)",
    ]
