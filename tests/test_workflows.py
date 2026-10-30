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

from nemik.tomlview import strings, table, tables
from nemik.workflows import advice_only

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "skills/nemik/SKILL.md").read_text()
SHAPES = files("nemik.data").joinpath("shapes.ttl").read_text()
MODEL = table(tomllib.loads(files("nemik.data").joinpath("workflows.toml").read_text()))
LIFECYCLE = table(MODEL["lifecycle"])
TRANSITIONS = tables(LIFECYCLE["transition"])
RULES = tables(MODEL["rule"])
COMMANDS = strings(table(MODEL["reference"])["commands"])
STEP_COMMANDS = [
    str(s["command"]) for w in tables(MODEL["workflow"]) for s in tables(w["steps"])
]


def test_every_transition_joins_declared_states() -> None:
    """Every transition joins declared states."""
    states = set(strings(LIFECYCLE["states"]))
    assert all({t["from"], t["to"]} <= states for t in TRANSITIONS)


def test_the_skill_teaches_every_lifecycle_command() -> None:
    """The skill teaches every lifecycle command."""
    taught = [str(t["command"]) for t in TRANSITIONS if str(t["command"]) in SKILL]
    missing = [
        str(t["command"]) for t in TRANSITIONS if str(t["command"]) not in taught
    ]
    assert not missing, f"skills/nemik/SKILL.md never teaches {missing}"


def test_every_enforcer_the_model_names_exists() -> None:
    """Every enforcer the model names exists."""
    declared = [e for t in TRANSITIONS for e in tables(t["enforced_by"])]
    declared += [e for r in RULES for e in tables(r["enforced_by"])]
    for e in declared:
        if "shape" in e:
            assert str(e["shape"]) in SHAPES, f"no shape message holds {e['shape']!r}"
        elif (
            ROOT / str(e["hook"])
        ).exists():  # the hook is not in a Bazel test sandbox
            assert str(e["text"]) in (ROOT / str(e["hook"])).read_text()


def test_the_skill_numbers_exactly_the_rules_the_model_declares() -> None:
    """The skill numbers exactly the rules the model declares."""
    rules = RULES
    section = SKILL.split("## The four rules that make the graph work")[1].split(
        "\n## "
    )[0]
    numbered = re.findall(r"^\d+\. \*\*(.+?)\*\*", section, flags=re.MULTILINE)
    assert len(numbered) == len(rules)
    for rule in rules:
        assert str(rule["skill_anchor"]) in section, (
            f"rule {rule['id']} has no anchor in SKILL.md"
        )


def test_every_workflow_step_command_appears_in_the_skill() -> None:
    """Every workflow step command appears in the skill."""
    assert [c for c in STEP_COMMANDS if c not in SKILL] == []


def test_every_documented_command_has_a_workflow_or_is_reference() -> None:
    """Every documented command has a workflow or is reference."""
    documented = re.findall(r"^\| `(nemik-[a-z-]+)", SKILL, flags=re.MULTILINE)
    placed = set(STEP_COMMANDS) | set(COMMANDS)
    assert [c for c in documented if c not in placed] == []
    # and the reference list names only commands the skill documents
    assert [c for c in COMMANDS if c not in documented] == []


def test_what_is_taught_but_not_enforced_is_the_reviewed_set() -> None:
    """Adding an unenforced transition or rule changes this set on purpose, in a reviewed diff."""
    assert advice_only(TRANSITIONS, RULES) == [
        "working->done (--status done)",
        "ready->dropped (--drop)",
    ]
