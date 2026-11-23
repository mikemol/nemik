# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2042: the pace asks for 3 days and widens the ratchets short of what it reads."""

from pathlib import Path

from nemik.hostroot_cli import NARROW_SINCE, RATCHET_SELECTOR, ratchet_export
from nemik.pacewiden import known_from, short_by_repo, widened_selector
from nemik.ratchetpace import MIN_WINDOWS, WINDOW

# samples enough for the observed fall and for the seed of what the ratchet owes
LONG = WINDOW * (MIN_WINDOWS + 1) + 2
SHORT = 3
WIDE = "30d"
TWICE = 2  # the quiet ratchet's line from the long answer and from the short one
ROOT = Path("store-root")
STEP_MS = 1000


def _line(repo: str, ratchet: str, samples: int) -> str:
    """Write one export line: a series of `samples` gate-run samples, one second apart.

    Returns:
        The line as the store's export writes it.

    """
    values = ", ".join(str(n) for n in range(samples, 0, -1))
    stamps = ", ".join(str(STEP_MS * (n + 1)) for n in range(samples))
    metric = f'{{"repo": "{repo}", "ratchet": "{ratchet}"}}'
    return f'{{"metric": {metric}, "values": [{values}], "timestamps": [{stamps}]}}'


def _series_text(pairs: list[tuple[str, str]]) -> str:
    """Write the store's series-list answer for the given (repo, ratchet) pairs.

    Returns:
        The answer text, {"status": "success", "data": [label sets]}.

    """
    labels = ", ".join(
        f'{{"__name__": "m", "repo": "{repo}", "ratchet": "{ratchet}"}}'
        for repo, ratchet in pairs
    )
    return f'{{"status": "success", "data": [{labels}]}}'


class _Store:
    """A store that answers from canned bodies and records what it was asked."""

    def __init__(self, pairs: list[tuple[str, str]], answers: dict[str, str]) -> None:
        self.pairs = pairs
        self.answers = answers
        self.calls: list[tuple[str, str]] = []

    def export(self, match: str, _root: Path, since: str) -> str:
        """Answer a raw export, keyed by a fragment of the selector.

        Returns:
            The canned body, or nothing.

        """
        self.calls.append((match, since))
        for fragment, body in self.answers.items():
            if fragment in match:
                return body
        return ""

    def series(self, _match: str, _root: Path) -> str:
        """Answer the series list.

        Returns:
            The series-list text.

        """
        return _series_text(self.pairs)


def test_the_series_list_gives_each_ratchet_with_both_labels() -> None:
    """A series without a repo or a ratchet label is left out, and a non-answer gives none."""
    text = (
        '{"status": "success", "data": [{"repo": "a", "ratchet": "x"}, {"repo": "b"}]}'
    )
    assert known_from(text) == [("a", "x")]
    assert known_from("not json") == []
    assert known_from('{"status": "error"}') == []


def test_a_ratchet_with_enough_samples_is_not_short() -> None:
    """Only the ratchets short of the pace's samples are asked again, grouped by repo."""
    pairs = [("a", "busy.json"), ("a", "quiet.json"), ("b", "quiet2.json")]
    text = "\n".join(
        [
            _line("a", "busy.json", LONG),
            _line("a", "quiet.json", SHORT),
            _line("b", "quiet2.json", SHORT),
        ]
    )
    assert short_by_repo(text, WINDOW, pairs) == {
        "a": ["quiet.json"],
        "b": ["quiet2.json"],
    }


def test_a_ratchet_with_no_sample_in_three_days_is_short_not_missing() -> None:
    """A ratchet quiet for days is in the series list and absent from the short export."""
    pairs = [("a", "busy.json"), ("aeternum", "*.py")]
    text = _line("a", "busy.json", LONG)
    assert short_by_repo(text, WINDOW, pairs) == {"aeternum": ["*.py"]}


def test_no_short_ratchet_gives_no_group() -> None:
    """A repo whose ratchets all hold enough samples is absent."""
    text = _line("a", "busy.json", LONG)
    assert short_by_repo(text, WINDOW, [("a", "busy.json")]) == {}


def test_the_selector_is_narrowed_to_one_repo_with_names_escaped() -> None:
    """A dot in a ratchet path matches itself, not any character."""
    narrowed = widened_selector(RATCHET_SELECTOR, "mtools", ["a/b.json", "c"])
    assert narrowed == (
        '{__name__="mikemol.ratchet.value",repo="mtools",ratchet=~"a/b\\\\.json|c"}'
    )


def test_enough_samples_in_three_days_make_one_call() -> None:
    """A busy ratchet needs no long window: one 3-day export, no widening."""
    store = _Store(
        [("a", "busy.json")], {"ratchet.value": _line("a", "busy.json", LONG)}
    )
    assert ratchet_export(ROOT, store.export, store.series)
    assert store.calls == [(RATCHET_SELECTOR, NARROW_SINCE)]


def test_a_quiet_ratchet_is_asked_again_over_the_long_window_alone() -> None:
    """Only the quiet ratchet's repo is widened, and it is asked for by name."""
    both = "\n".join([_line("a", "busy.json", LONG), _line("a", "quiet.json", SHORT)])
    answers = {'repo="a"': _line("a", "quiet.json", LONG), "ratchet.value": both}
    store = _Store([("a", "busy.json"), ("a", "quiet.json")], answers)
    text = ratchet_export(ROOT, store.export, store.series)
    assert [since for _, since in store.calls] == [NARROW_SINCE, WIDE]
    assert 'ratchet=~"quiet\\\\.json"' in store.calls[1][0]
    assert "busy" in text
    assert text.count("quiet.json") == TWICE


def test_a_ratchet_quiet_for_days_is_widened_not_dropped() -> None:
    """A ratchet with no sample in the short window is asked for over the long one."""
    answers = {'repo="aeternum"': _line("aeternum", "*.py", LONG)}
    store = _Store([("aeternum", "*.py")], answers)
    text = ratchet_export(ROOT, store.export, store.series)
    assert "aeternum" in text
    assert [since for _, since in store.calls] == [NARROW_SINCE, WIDE]


def test_a_widen_that_fails_raises_so_the_run_keeps_the_old_file() -> None:
    """A store that fails on the widen raises OSError, which pace_fetch reports as exit 1."""
    quiet = _line("a", "quiet.json", SHORT)

    def failing(_match: str, _root: Path, since: str) -> str:
        if since == WIDE:
            message = "the store's export answered 500"
            raise OSError(message)
        return quiet

    store = _Store([("a", "quiet.json")], {})
    caught = ""
    try:
        ratchet_export(ROOT, failing, store.series)
    except OSError as error:
        caught = str(error)
    assert "500" in caught
