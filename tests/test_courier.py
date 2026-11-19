# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2280: the courier send is off unless the operator's config says so."""

import pytest

from nemik.courier import BadRepoError, SendDisabledError, dry_run, enabled, send_argv

REPO = "mikemol/luthen-observability"
TITLE = "nemik:W2280 asks: a title with 'quotes', $(subshell) and ; separators"
BODY = 'line one\nline two with `ticks` and a "quote"\n'
ON = "# the operator's courier config\ncourier_send = true\n"


def test_the_dry_run_prints_repo_title_and_body_and_says_nothing_was_sent() -> None:
    """The text an operator reads before any send: the three fields, and that it sent nothing."""
    text = dry_run(REPO, TITLE, BODY)
    assert text.startswith("DRY RUN: nothing sent\n")
    assert f"repo: {REPO}\n" in text
    assert f"title: {TITLE}\n" in text
    assert text.endswith(f"body:\n{BODY}\n")


@pytest.mark.parametrize(
    "config",
    [
        "",
        "courier_send = false\n",
        "# courier_send = true\n",
        "courier_send = yes\n",
        "courier_send = true\ncourier_send = false\n",
        "other = true\n",
    ],
)
def test_a_send_is_refused_unless_the_config_reads_true(config: str) -> None:
    """Off by default: no line, a false or other value, a comment, or a later false all refuse."""
    assert not enabled(config)
    with pytest.raises(SendDisabledError):
        send_argv(REPO, TITLE, BODY, config)


def test_an_enabled_send_is_one_gh_api_command_with_text_as_single_arguments() -> None:
    """The argv holds the title and body whole, each in one argument, so no shell parses them."""
    assert enabled(ON)
    assert send_argv(REPO, TITLE, BODY, ON) == [
        "gh",
        "api",
        f"repos/{REPO}/issues",
        "--method",
        "POST",
        "-f",
        f"title={TITLE}",
        "-f",
        f"body={BODY}",
    ]


def test_the_last_courier_send_line_wins() -> None:
    """A later line turns it back off, and a later true turns it on."""
    assert not enabled("courier_send = true\ncourier_send = false\n")
    assert enabled("courier_send = false\ncourier_send = true\n")


def test_the_dry_run_and_the_send_carry_the_same_fields() -> None:
    """What the operator approves from the dry run is exactly what the command would create."""
    text = dry_run(REPO, TITLE, BODY)
    argv = send_argv(REPO, TITLE, BODY, ON)
    assert f"title: {TITLE}\n" in text
    assert f"title={TITLE}" in argv
    assert text.endswith(f"body:\n{BODY}\n")
    assert f"body={BODY}" in argv


@pytest.mark.parametrize(
    "repo", ["", "mikemol", "mikemol/", "/luthen", "a/b/c", "mikemol/with space"]
)
def test_a_repo_that_is_not_owner_slash_name_is_refused_by_both(repo: str) -> None:
    """A malformed repo reaches neither the dry run nor the command."""
    with pytest.raises(BadRepoError):
        dry_run(repo, TITLE, BODY)
    with pytest.raises(BadRepoError):
        send_argv(repo, TITLE, BODY, ON)
