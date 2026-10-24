# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W533: the converge loop ends clean or stuck, gives up on a repeat, or hits a ceiling."""

from mikemol.converge.converge import HALT, Policy, Verdict, World, converge

POLICY = Policy(done=[0, 4], max_passes=5, same_halt=3, pauses=2)


def _key(verdict: Verdict) -> str:
    """Name a halt by its why.

    Args:
        verdict: A pass's verdict.

    Returns:
        The why, as text.

    """
    return str(verdict.get("why", ""))


def _go(
    script: list[tuple[int, Verdict]],
) -> tuple[tuple[int, Verdict], list[Verdict], list[int]]:
    """Run the loop on a scripted world with trigger "acute".

    Args:
        script: The (code, verdict) each pass returns, in order.

    Returns:
        The loop's (code, verdict), the rows recorded, and the pauses taken (one entry each).

    """
    todo = list(script)
    rows: list[Verdict] = []
    pauses: list[int] = []
    world = World(
        run_pass=lambda: todo.pop(0),
        record=rows.append,
        pause=lambda: pauses.append(1),
        halt_key=_key,
    )
    return converge(world, POLICY, "acute"), rows, pauses


def test_a_clean_first_pass_returns_at_once() -> None:
    """Exit 0 on pass 1: one row, no pause, passes added to the verdict."""
    result, rows, pauses = _go([(0, {"state": "done"})])
    assert result == (0, {"state": "done", "passes": 1})
    assert len(rows) == 1
    assert not pauses


def test_a_halt_that_clears_is_retried_with_pauses_between() -> None:
    """A halt then a clean pass: two rows, one gap of the policy's pauses."""
    (code, verdict), rows, pauses = _go([(1, {"why": "not ready"}), (0, {})])
    assert code == 0
    assert verdict["passes"] == len(rows)
    assert len(pauses) == POLICY.pauses


def test_the_same_halt_in_a_row_gives_up() -> None:
    """Three identical halts: HALT with the reason, not five passes."""
    (code, verdict), _, _ = _go([(1, {"why": "x"})] * 5)
    assert code == HALT
    assert verdict["passes"] == POLICY.same_halt
    assert "cannot clear" in str(verdict["converge"])


def test_changing_halts_run_to_the_ceiling() -> None:
    """Different halts every pass never repeat: the loop stops at the pass ceiling."""
    script: list[tuple[int, Verdict]] = [
        (1, {"why": str(i)}) for i in range(POLICY.max_passes)
    ]
    (code, verdict), _, _ = _go(script)
    assert code == HALT
    assert verdict["passes"] == POLICY.max_passes
    assert "ceiling" in str(verdict["converge"])


def test_every_row_names_its_trigger_and_pass() -> None:
    """Each recorded row carries trigger, n and exit."""
    _, rows, _ = _go([(1, {"why": "a"}), (4, {"state": "stuck"})])
    assert [(r["trigger"], r["n"], r["exit"]) for r in rows] == [
        ("acute", 1, 1),
        ("acute", 2, 4),
    ]


def test_the_decided_trigger_words_pass_through_to_the_row() -> None:
    """nemik:W533: luthen's three words (acute, chronic, hand) are recorded as given, never mapped.

    luthen-observability:W1501 decided them (2026-10-24): acute is a pass started by the set's path
    unit on an input event, chronic one started because the epoch stamp was bumped, hand a person
    or a session. Its nudge counts three consecutive chronic passes ending the same way; that
    counting is luthen's, so the library only has to carry the word.
    """
    seen: list[str] = []
    for word in ("acute", "chronic", "hand"):
        rows: list[Verdict] = []
        world = World(
            run_pass=lambda: (0, {}),
            record=rows.append,
            pause=lambda: None,
            halt_key=_key,
        )
        converge(world, POLICY, word)
        seen.append(str(rows[0]["trigger"]))
    assert seen == ["acute", "chronic", "hand"]


def test_the_verdict_is_nested_in_the_row() -> None:
    """The run-row reader takes verdict.state from an object, so the verdict is not flattened."""
    _, rows, _ = _go([(4, {"state": "stuck"})])
    assert rows[0]["verdict"] == {"state": "stuck"}
    assert "state" not in rows[0]
