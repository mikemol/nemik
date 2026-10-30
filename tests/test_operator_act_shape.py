# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W458: an operator act ask with no command in the standard shape is the owner's debt."""

from nemik.blocks import errand_repos, operator_category

ENV = "env -C /home/m/github/luthen /usr/bin/python3 -m luthen.apply --set tpm"


def test_an_act_with_nothing_to_run_is_no_command() -> None:
    """An act with nothing to run is no command."""
    # luthen-observability:W69's ask, as it stood for 93 ticks: "sudo" here is prose, not a command
    assert operator_category("operator: act the host-root sudo applies") == "no-command"
    assert operator_category("operator: act run the reaper (root)") == "no-command"


def test_an_act_with_a_standard_command_needs_the_operator() -> None:
    """An act with a standard command needs the operator."""
    sysd = "sudo systemctl stop luthen-tier-send.timer"
    for cmd in (ENV, "sudo /usr/local/bin/apply-host", f"sudo -E {ENV}", sysd):
        assert operator_category(f"operator: act {cmd}") == "needs-you"


def test_an_errand_is_the_operators_not_a_tool() -> None:
    """An errand is the operators not a tool."""
    errand = "operator: act bring to orientation Mon 8 AM"
    assert operator_category(errand) == "needs-you"


def test_a_decision_is_unchanged() -> None:
    assert operator_category("operator: decide which store") == "needs-you"


def test_errand_repos_are_declared() -> None:
    # nemik:W460: a machine-sounding act in these repos is an errand, not an unwritten tool
    assert errand_repos('[errand]\nrepos = ["life"]\n') == {"life"}
    assert errand_repos("") == frozenset()
    assert "life" in errand_repos()  # the shipped declaration (github-8f ruling)
