"""nemik:W177: a repo keeps exactly one working card unless every open item is blocked."""

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri, workstream_uri
from nemik.blocks import annotate


def _repo(g, repo, *statuses):
    ws = workstream_uri(repo)
    for i, st in enumerate(statuses, 1):
        n = waypoint_uri(repo, f"W{i}")
        g.add((n, OSLC_CM.state, STATE[st]))
        g.add((n, NEMIK.workstream, ws))
    return ws


def test_ready_items_and_no_working_card_is_flagged() -> None:
    g = Graph()
    ws = _repo(g, "a", "ready", "ready", "blocked")
    annotate(g)
    assert [int(str(o)) for o in g.objects(ws, NEMIK.noActiveCard)] == [2]


def test_exactly_one_working_card_is_clean() -> None:
    g = Graph()
    ws = _repo(g, "a", "working", "ready", "blocked")
    annotate(g)
    assert (ws, NEMIK.noActiveCard, None) not in g and (
        ws,
        NEMIK.extraActiveCards,
        None,
    ) not in g


def test_several_working_cards_are_flagged() -> None:
    g = Graph()
    ws = _repo(g, "a", "working", "working", "working")
    annotate(g)
    assert [int(str(o)) for o in g.objects(ws, NEMIK.extraActiveCards)] == [3]


def test_all_blocked_or_done_needs_no_card() -> None:
    g = Graph()
    ws = _repo(g, "a", "blocked", "blocked", "done")
    annotate(g)
    assert (ws, NEMIK.noActiveCard, None) not in g
