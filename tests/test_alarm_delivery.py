"""nemik:W166: each alarm firing is delivered once, keyed (ref, RECURRENCE-ID, instant)."""

from nemik.wake import alarm_key, undelivered


def _a(at, rid="", ref="life:W12"):
    return {"ref": ref, "recurrence_id": rid, "at": at, "trigger": "-PT15M"}


def test_a_firing_is_delivered_once_across_overlapping_windows() -> None:
    seen: dict = {}
    first = undelivered([_a("2026-10-01T13:00:00Z")], seen)
    again = undelivered([_a("2026-10-01T13:00:00Z")], seen)
    assert len(first) == 1 and again == []


def test_occurrences_and_instants_are_distinct() -> None:
    seen: dict = {}
    rows = [
        _a("2026-10-01T13:00:00Z", "20261001"),
        _a("2026-10-02T13:00:00Z", "20261002"),
        _a("2026-10-01T12:00:00Z", "20261001"),
    ]  # a second alarm on the same occurrence
    assert len(undelivered(rows, seen)) == 3


def test_errors_are_never_marked_delivered() -> None:
    seen: dict = {}
    bad = {**_a(""), "error": "bad trigger"}
    assert (
        undelivered([bad], seen) == [bad]
        and undelivered([bad], seen) == [bad]
        and seen == {}
    )


def test_alarm_keys_cannot_collide_with_repo_keys() -> None:
    assert "|" in alarm_key(_a("x"))
