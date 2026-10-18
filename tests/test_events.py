# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W370: issue events become printed lines, never a queue write.

The payloads are shaped after the issues and issue_comment events GitHub and Forgejo document
(action, issue{number,title,body,html_url}, repository{full_name}, comment{body,user{login}}); they
are written here, not recorded from a live tracker.
"""

from nemik.events import lines, mirrored_cite, quote, title_of

OPENED = (
    '{"action": "opened", "repository": {"full_name": "acme/widgets"},'
    ' "issue": {"number": 7, "title": "Fix the thing; then the other", "body": "plain",'
    ' "html_url": "https://forge.example/acme/widgets/issues/7"}}'
)
MIRRORED_CLOSED = (
    '{"action": "closed", "repository": {"full_name": "acme/widgets"},'
    ' "issue": {"number": 8, "title": "t", "body": "nemik card nemik:W369",'
    ' "html_url": "https://forge.example/acme/widgets/issues/8"}}'
)
COMMENT = (
    '{"action": "created", "repository": {"full_name": "acme/widgets"},'
    ' "issue": {"number": 9, "title": "t", "body": "nemik card nemik:W370",'
    ' "html_url": "u"}, "comment": {"body": "please look", "user": {"login": "pat"}}}'
)
URL = "https://forge.example/acme/widgets/issues/7"


def test_an_opened_issue_prints_the_command_that_would_mint_its_card() -> None:
    """The title loses its `;` (the writer refuses it) and is quoted; nothing is run."""
    got = lines(OPENED)
    assert got[0] == f"# acme/widgets#7 opened: {URL}"
    assert got[1] == (
        "mikemol-paths-forward --state .claude/paths-forward.json"
        " --add 'Fix the thing, then the other'"
    )


def test_a_closed_mirrored_issue_suggests_done_for_its_card() -> None:
    """The cite in the body names the card; the status change is a comment, not a command."""
    got = lines(MIRRORED_CLOSED)
    assert got[1].startswith("# suggest, if nemik:W369 is this repo's card: ")
    assert got[1].endswith("--update W369 --status done")


def test_a_comment_becomes_a_letter_body_for_the_owning_repo() -> None:
    """Who said what, on which issue, and the words."""
    got = lines(COMMENT)
    assert got[1] == "# letter for the inbox of the repo that owns nemik:W370:"
    assert got[2:] == ["pat commented on acme/widgets#9:", "please look"]


def test_events_nemik_does_not_read_print_nothing() -> None:
    """Torn JSON, a missing field, an opened issue nemik wrote, a comment with no body."""
    assert lines("{") == []
    assert lines('{"action": "opened"}') == []
    assert lines(OPENED.replace('"plain"', '"nemik card x:W1"')) == []
    assert lines(COMMENT.replace("please look", "")) == []


def test_helpers() -> None:
    """Quoting, the title rule and the mirror marker."""
    assert quote("it's") == "'it'\\''s'"
    assert title_of("a" * 400) == "a" * 150
    assert mirrored_cite("see nemik card alpha:W5 here") == "alpha:W5"
    assert not mirrored_cite("nothing")
