# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W320: the workflow model (data/workflows.toml) matches skills/nemik/SKILL.md and the code.

Each direction is checked, so a rule the skill teaches but the model lacks, or a model step the
skill never mentions, fails here.
"""

from __future__ import annotations

import re
import tomllib
from importlib.resources import files
from pathlib import Path

from nemik.workflows import advice_only

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "skills/nemik/SKILL.md").read_text()
SHAPES = files("nemik.data").joinpath("shapes.ttl").read_text()
MODEL = tomllib.loads(files("nemik.data").joinpath("workflows.toml").read_text())
TRANSITIONS = MODEL["lifecycle"]["transition"]


def test_every_transition_joins_declared_states() -> None:
    """Every transition joins declared states."""
    states = set(MODEL["lifecycle"]["states"])
    assert all({t["from"], t["to"]} <= states for t in TRANSITIONS)


def test_the_skill_teaches_every_lifecycle_command() -> None:
    """The skill teaches every lifecycle command."""
    taught = [t["command"] for t in TRANSITIONS if t["command"] in SKILL]
    missing = [t["command"] for t in TRANSITIONS if t["command"] not in taught]
    assert not missing, f"skills/nemik/SKILL.md never teaches {missing}"


def test_every_enforcer_the_model_names_exists() -> None:
    """Every enforcer the model names exists."""
    declared = [e for t in TRANSITIONS for e in t["enforced_by"]]
    declared += [e for r in MODEL["rule"] for e in r["enforced_by"]]
    for e in declared:
        if "shape" in e:
            assert e["shape"] in SHAPES, f"no shape message holds {e['shape']!r}"
        elif (ROOT / e["hook"]).exists():  # the hook is not in a Bazel test sandbox
            assert e["text"] in (ROOT / e["hook"]).read_text()


def test_the_skill_numbers_exactly_the_rules_the_model_declares() -> None:
    """The skill numbers exactly the rules the model declares."""
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
    """Every workflow step command appears in the skill."""
    commands = [s["command"] for w in MODEL["workflow"] for s in w["steps"]]
    assert [c for c in commands if c not in SKILL] == []


def test_every_documented_command_has_a_workflow_or_is_reference() -> None:
    """Every documented command has a workflow or is reference."""
    table = re.findall(r"^\| `(nemik-[a-z-]+)", SKILL, flags=re.MULTILINE)
    steps = {s["command"] for w in MODEL["workflow"] for s in w["steps"]}
    placed = steps | set(MODEL["reference"]["commands"])
    assert [c for c in table if c not in placed] == []
    # and the reference list names only commands the skill documents
    assert [c for c in MODEL["reference"]["commands"] if c not in table] == []


def test_what_is_taught_but_not_enforced_is_the_reviewed_set() -> None:
    """Adding an unenforced transition or rule changes this set on purpose, in a reviewed diff."""
    assert advice_only(TRANSITIONS, MODEL["rule"]) == [
        "working->done (--status done)",
        "ready->dropped (--drop)",
    ]
