# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2176: an operator act that has the operator hand-supply a credential is flagged.

The motivating instance is luthen-observability:W703, which asked the operator to set
TAILSCALE_OAUTH_CLIENT_ID and TAILSCALE_OAUTH_CLIENT_SECRET while luthen's own W690 evidence
named the file that holds them (github-cb, operator 2026-11-13); luthen has since rewritten the ask,
so the W703 constant below is its original text from git history. The rule has three parts, each
tested here:
the text rule (nemik.blocks.credential_shaped), the excuse line in the evidence
('no machine-held source: <reason, card>', read by nemik.adapter), and the SHACL Warning shape and
the nemik-operator --credential-shaped mode that report it.
"""

import json
from typing import TYPE_CHECKING

import pytest
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import XSD

from nemik.adapter import NEMIK, OSLC_CM, no_machine_source, queue_graph
from nemik.blocks import credential_shaped
from nemik.blocks_cli import operator_main
from nemik.check import shapes
from nemik.shaclinc import findings

if TYPE_CHECKING:
    from pathlib import Path

SAID = "hand-supply a credential"
# luthen-observability:W703's ORIGINAL ask, verbatim: read (read-only) from luthen-observability's
# git history, `git grep TAILSCALE_OAUTH_CLIENT_SECRET f440e0ad -- .claude/paths-forward.json`, the
# commit before luthen rewrote the ask. It names the two variables AND "the credential held outside
# the tree", so it matches the rule two ways.
W703 = (
    "operator: act with TAILSCALE_OAUTH_CLIENT_ID and TAILSCALE_OAUTH_CLIENT_SECRET set in your "
    "shell from the credential held outside the tree, run: tofu -chdir=/home/mikemol/github/"
    "luthen-observability/terraform/tailnet init, then tofu -chdir=/home/mikemol/github/"
    "luthen-observability/terraform/tailnet import tailscale_acl.policy acl, then tofu -chdir="
    "/home/mikemol/github/luthen-observability/terraform/tailnet plan. Done when the plan prints "
    "'No changes.' (any diff: paste it to the session, do not apply)."
)
# the first draft of luthen-observability:W2623, as relayed by github-cb
W2623_DRAFT = "operator: act the operator writes the secret once, into the unit's environment"


def _judged(key: str, blocked_on: str, *, excused: bool) -> list[str]:
    """Judge one blocked card against the shapes.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        blocked_on: The card's blocked_on text.
        excused: Whether the card's evidence has a 'no machine-held source:' line.

    Returns:
        The messages the shapes report.

    """
    g = Graph()
    card = URIRef(f"urn:test:card/{key}")
    g.add((card, RDF.type, OSLC_CM.ChangeRequest))
    g.add((card, OSLC_CM.state, NEMIK.Blocked))
    g.add((card, NEMIK.blockedOn, Literal(blocked_on)))
    if excused:
        g.add((card, NEMIK.noMachineSource, Literal("true", datatype=XSD.boolean)))
    return [m for _, _, m in findings(f"cred-{key}", g, shapes())]


def _says(messages: list[str]) -> bool:
    """Say whether any message is the credential shape's.

    Returns:
        True when one of the messages is the shape's.

    """
    return any(SAID in m for m in messages)


@pytest.mark.parametrize(
    "ask",
    [
        W703,
        W2623_DRAFT,
        "operator: act export GITHUB_TOKEN=... before the run",
        "operator: act paste the API key into the prompt",
        "operator: act type the password when asked",
        "operator: act put the credential held outside the tree into place",
        "operator: act set CLOUDFLARE_API_KEY in the unit",
    ],
)
def test_an_act_ask_that_has_the_operator_supply_a_credential_is_credential_shaped(
    ask: str,
) -> None:
    """The text rule flags each way the ask can have the operator carry a secret."""
    assert credential_shaped(ask)


@pytest.mark.parametrize(
    "ask",
    [
        "operator: decide whether to rotate the token",
        "operator: act review the keyboard layout notes",
        "operator: act approve the deploy",
        "operator: act restart the unit",
        "operator: act rotate the key through the vault",
        "approve the secret store design",
    ],
)
def test_other_asks_are_not_credential_shaped(ask: str) -> None:
    """A decide ask, a longer word, and an act with no credential in it are not flagged."""
    assert not credential_shaped(ask)


def test_the_shape_warns_on_w703_and_the_text_rule_agrees() -> None:
    """The live instance: the shape's Warning and credential_shaped both fire on W703's wording."""
    assert credential_shaped(W703)
    assert _says(_judged("w703", W703, excused=False))


def test_the_shape_warns_on_the_w2623_draft() -> None:
    """The same shape again: 'the operator writes the secret once'."""
    assert _says(_judged("w2623", W2623_DRAFT, excused=False))


def test_the_excuse_line_clears_the_warning() -> None:
    """MUTANT: the same ask with the evidence line is not warned; without it, it is."""
    assert _says(_judged("plain", W703, excused=False))
    assert not _says(_judged("excused", W703, excused=True))


def test_a_decide_ask_is_not_warned() -> None:
    """Only an act ask counts."""
    assert not _says(
        _judged("decide", "operator: decide whether to set the token", excused=False)
    )


def test_a_line_with_a_reason_counts() -> None:
    """The excuse starts the way it is worded and gives a reason and a card."""
    text = "a note\nno machine-held source: the vendor shows it once, luthen-observability:W9\nmore"
    assert no_machine_source(text)


def test_a_line_with_no_reason_does_not() -> None:
    """The colon with nothing after it is not an exception."""
    assert not no_machine_source("no machine-held source:\n")
    assert not no_machine_source("no machine-held source:   ")


def test_the_phrase_inside_a_sentence_does_not() -> None:
    """The line has to start with the phrase, not carry it mid-sentence."""
    assert not no_machine_source("there is no machine-held source: so ask")


def test_the_graph_carries_the_excuse_for_a_card_that_says_so(tmp_path: Path) -> None:
    """A card with the line gets the predicate; the same card without it does not."""
    cards = [
        {
            "symbol": "W1",
            "title": "says it",
            "status": "blocked",
            "blocked_on": ["operator: act set X_TOKEN"],
            "blocked_kind": "human",
            "evidence": "no machine-held source: the vendor shows it once, luthen:W9",
        },
        {
            "symbol": "W2",
            "title": "does not",
            "status": "blocked",
            "blocked_on": ["operator: act set Y_TOKEN"],
            "blocked_kind": "human",
            "evidence": "nothing about a source",
        },
    ]
    state = {
        "version": 1,
        "project_root": str(tmp_path),
        "counter": 2,
        "residue": [],
        "waypoints": cards,
    }
    path = tmp_path / "paths-forward.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    g = queue_graph("a", path)
    true = Literal("true", datatype=XSD.boolean)
    said = {str(s) for s in g.subjects(NEMIK.noMachineSource, true)}
    assert len(said) == 1
    assert next(iter(said)).endswith("W1")


def _root(tmp_path: Path, blocked_on: str, evidence: str) -> Path:
    """Write one repo's queue under a root.

    Returns:
        The root directory holding the repo.

    """
    queue = tmp_path / "a" / ".claude"
    queue.mkdir(parents=True)
    card = {
        "symbol": "W1",
        "title": "t",
        "status": "blocked",
        "blocked_on": [blocked_on],
        "blocked_kind": "human",
        "evidence": evidence,
    }
    state = {
        "version": 1,
        "project_root": str(tmp_path / "a"),
        "counter": 1,
        "residue": [],
        "waypoints": [card],
    }
    (queue / "paths-forward.json").write_text(json.dumps(state), encoding="utf-8")
    return tmp_path


def test_the_mode_exits_1_and_prints_the_flagged_ask(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A credential-supplying act ask with no excuse prints and exits 1."""
    root = _root(tmp_path, W703, "nothing")
    with pytest.raises(SystemExit) as stopped:
        operator_main(["--credential-shaped", "--root", str(root)])
    assert stopped.value.code == 1
    assert "a:W1" in capsys.readouterr().out


def test_the_mode_exits_0_when_the_card_is_excused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same ask with the excuse line prints nothing and does not exit."""
    root = _root(
        tmp_path, W703, "no machine-held source: the vendor shows it once, luthen:W9"
    )
    operator_main(["--credential-shaped", "--root", str(root)])
    assert not capsys.readouterr().out
