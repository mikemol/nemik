# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W782: every read-only CLI command is served, pending a named card, or excluded."""

from pathlib import Path

from nemik.parity import EXCLUDED, PENDING, ROUTED

ROOT = Path(__file__).resolve().parents[1]
SERVE = ROOT / "src" / "nemik" / "serve.py"
# The pending list only shrinks: lower this as W784 to W786 add their routes.
PENDING_MOST = 11


def _commands() -> set[str]:
    """Read the nemik-* console scripts out of pyproject.toml's [project.scripts].

    Returns:
        Their names.

    """
    text = (ROOT / "pyproject.toml").read_text()
    section = text.partition("[project.scripts]")[2].partition("\n[")[0]
    names = [line.partition("=")[0].strip() for line in section.splitlines()]
    return {name for name in names if name.startswith("nemik-")}


def _declared() -> list[str]:
    """List every command the three lists name, with repeats.

    Returns:
        The names, routed then pending then excluded.

    """
    rows = [*ROUTED, *PENDING, *EXCLUDED]
    return [row[0] for row in rows]


def test_every_command_is_in_exactly_one_list() -> None:
    """A new nemik-* script must be routed, pending or excluded by a reason, never absent."""
    declared = _declared()
    assert sorted(_commands() - set(declared)) == [], "in no list"
    assert sorted(set(declared) - _commands()) == [], "named but not a script"
    assert sorted(name for name in set(declared) if declared.count(name) > 1) == []


def test_a_routed_row_names_a_route_and_a_function_the_server_carries() -> None:
    """The route is one the handler answers and the function is one serve.py calls."""
    source = SERVE.read_text()
    for command, route, function in ROUTED:
        assert route in source, f"{command}: serve.py answers no {route}"
        assert function in source, f"{command}: serve.py never uses {function}"


def test_a_pending_row_names_the_card_that_adds_its_route() -> None:
    """Each pending command waits on a card in the parity goal, W784 to W786."""
    cards = {card for _, card in PENDING}
    assert cards <= {"W784", "W785", "W786"}
    assert len(PENDING) <= PENDING_MOST


def test_an_exclusion_states_its_reason() -> None:
    """A command is left unserved by a stated reason, not by omission."""
    assert [command for command, reason in EXCLUDED if not reason.strip()] == []
