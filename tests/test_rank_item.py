# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2321: rank --item says whether a card is in the ranked list and, when not, why."""

import pytest
from rdflib import Graph, Literal, URIRef

from nemik import rank
from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri, workstream_uri
from nemik.rank import NotRankedError, require_ranked
from nemik.score import load_weights

REPO = "a"


def _card(g: Graph, sym: str, status: str, feeds: tuple[str, ...] = ()) -> URIRef:
    """Add a waypoint of repo a, and an enables edge from each card named in `feeds`.

    Returns:
        The waypoint's node.

    """
    n = waypoint_uri(REPO, sym)
    g.add((n, NEMIK.symbol, Literal(sym)))
    g.add((n, NEMIK.workstream, workstream_uri(REPO)))
    g.add((n, OSLC_CM.state, STATE[status]))
    for feeder in feeds:
        g.add((waypoint_uri(REPO, feeder), NEMIK.enables, n))
    return n


def _fixture() -> Graph:
    """W1 is a ready umbrella fed by the ready leaf W2 and the done W3; W4 is blocked.

    Returns:
        The graph.

    """
    g = Graph()
    _card(g, "W1", "ready", ("W2", "W3"))
    _card(g, "W2", "ready")
    _card(g, "W3", "done")
    _card(g, "W4", "blocked")
    return g


def _item(g: Graph, sym: str, capsys: pytest.CaptureFixture[str]) -> str:
    """Run `nemik-rank --item` over the graph.

    Returns:
        What it printed.

    """
    rank.main(["--item", f"{REPO}:{sym}", REPO], g)
    return capsys.readouterr().out


def _listed(g: Graph, sym: str, *, with_working: bool = False) -> bool:
    """Ask `require_ranked` about one card, as a yes or a no.

    Returns:
        True when it returns, False when it raises NotRankedError.

    """
    try:
        require_ranked(g, waypoint_uri(REPO, sym), with_working=with_working)
    except NotRankedError:
        return False
    return True


def test_a_ready_leaf_is_in_the_list_and_says_so(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Nothing is raised for a listed card, and --item prints that it is in the list."""
    g = _fixture()
    require_ranked(g, waypoint_uri(REPO, "W2"))
    out = _item(g, "W2", capsys)
    assert "a:W2 is in the ranked list" in out
    assert "not in the ranked list" not in out


def test_a_ready_umbrella_is_named_with_its_feeders_and_the_leaves_ranked_instead(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The case the card was minted for: ready, yet not ranked, and the reason is the frontier."""
    g = _fixture()
    with pytest.raises(NotRankedError) as raised:
        require_ranked(g, waypoint_uri(REPO, "W1"))
    why = str(raised.value)
    assert "umbrella" in why
    assert "a:W2 feed it" in why
    assert "a:W3" not in why  # a done feeder is not open work
    assert "ranked in its place are a:W2" in why
    out = _item(g, "W1", capsys)
    assert "a:W1 is not in the ranked list: it is an umbrella" in out


def test_a_done_and_a_blocked_card_are_not_ranked_because_only_ready_cards_are(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A card in another state is named by that state."""
    g = _fixture()
    with pytest.raises(NotRankedError, match=r"^it is done, and only ready cards are"):
        require_ranked(g, waypoint_uri(REPO, "W3"))
    assert "it is blocked, and only ready cards are ranked" in _item(g, "W4", capsys)


def test_a_working_card_is_listed_only_when_the_round_asks_for_the_working() -> None:
    """The same switch `rank` has: with_working adds the cards in progress."""
    g = Graph()
    n = _card(g, "W9", "working")
    with pytest.raises(NotRankedError):
        require_ranked(g, n)
    require_ranked(g, n, with_working=True)


@pytest.mark.parametrize(
    "options", [rank.RankOptions(), rank.RankOptions(with_working=True)]
)
def test_the_verdict_agrees_with_rank_for_every_card(
    options: rank.RankOptions,
) -> None:
    """A card is in `rank`'s list exactly when `require_ranked` returns."""
    g = _fixture()
    _card(g, "W8", "working")
    listed = {r["symbol"] for r in rank.rank(g, REPO, load_weights(), options=options)}
    for sym in ("W1", "W2", "W3", "W4", "W8"):
        said = _listed(g, sym, with_working=options.with_working)
        assert said == (sym in listed), sym
