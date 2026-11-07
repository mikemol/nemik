# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: the hook check builds Claude Code's payload and judges a hook's exit."""

from hookcheck import HOOKS, main, payload, verdict

USAGE_ERROR = 2
TRACEBACK = "Traceback (most recent call last):"


def test_the_payload_is_the_one_line_json_claude_code_sends() -> None:
    """The payload names the event, the Bash tool and a harmless command."""
    text = payload("PreToolUse")
    assert '"hook_event_name": "PreToolUse"' in text
    assert '"tool_name": "Bash"' in text
    assert "\n" not in payload("PostToolUse")


def test_a_hook_that_exits_zero_without_a_traceback_is_ok() -> None:
    """Exit 0 and a quiet stderr read OK."""
    assert verdict("h", "PreToolUse", 0, "").startswith("OK")
    assert verdict("h", "PreToolUse", 0, "a warning only").startswith("OK")


def test_a_nonzero_exit_or_a_traceback_is_a_failure_naming_the_first_line() -> None:
    """A bad exit status or a printed traceback reads FAIL with the first stderr line."""
    nonzero = verdict("h", "PreToolUse", 1, "boom\nmore")
    assert nonzero.startswith("FAIL")
    assert "boom" in nonzero
    assert verdict("h", "PostToolUse", 0, TRACEBACK).startswith("FAIL")


def test_the_hooks_checked_are_the_two_that_import_nemik() -> None:
    """Both nemik hooks are exercised on both events."""
    assert {hook for hook, _ in HOOKS} == {
        "mikemol-hook-inbound-asks",
        "mikemol-hook-nemik-check",
    }
    assert {event for _, event in HOOKS} == {"PreToolUse", "PostToolUse"}


def test_a_wrong_number_of_arguments_is_a_usage_error() -> None:
    """The check takes the venv bin and the source directory, and nothing else."""
    assert main(["only-one"]) == USAGE_ERROR
    assert main([]) == USAGE_ERROR
