# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1094: a live loop whose ledger has no recent tick line is a Warning.

The signal is a live loop (luthen's liveness export, verdict ok) with a stale newest tick line:
most repos are dormant on purpose, so a stale tick alone is not a finding. Silence is UNKNOWN, not
clean (github-cb 2026-11-16): with no readable export every live loop is unjudged, so that is its
own finding, and the answer of live_repos is two parts, never a maybe.
"""

import calendar
import json
from importlib.resources import files
from typing import TYPE_CHECKING

from nemik.idle import declared_stale_minutes, live_repos, stale_findings

if TYPE_CHECKING:
    from pathlib import Path

NOW = float(calendar.timegm((2026, 11, 15, 12, 0, 0)))
FRESH = '2026-11-15T11:45:00Z  tick  W1  advanced  unblock  "fifteen minutes ago"\n'
STALE = '2026-11-10T18:06:42Z  tick  W1  advanced  unblock  "four days ago"\n'
PEER = '2026-11-15T11:59:00Z  peer  W1  advanced  msg      "a peer, not a tick"\n'
DECLARED = 90
SMALL = 5
PACKAGED = files("nemik.data").joinpath("rank-weights.toml").read_text()


def _fleet(
    root: Path, ledgers: dict[str, str], verdicts: dict[str, str] | None
) -> None:
    """Write each repo's ledger and, when given, a liveness export with the verdicts.

    Args:
        root: The fleet root.
        ledgers: Ledger text by repo.
        verdicts: Liveness verdict by repo, or None for no export.

    """
    for repo, text in ledgers.items():
        claude = root / repo / ".claude"
        claude.mkdir(parents=True)
        (claude / "paths-forward.ledger").write_text(text, encoding="utf-8")
    if verdicts is not None:
        document = {"repos": {r: {"verdict": v} for r, v in verdicts.items()}}
        (root / "liveness.json").write_text(json.dumps(document), encoding="utf-8")


def test_the_declared_bound_comes_from_rank_weights() -> None:
    """The bound is read from the text it is given, with a default, and not typed in the check."""
    assert declared_stale_minutes(PACKAGED) == DECLARED
    assert declared_stale_minutes("[idle]\ntick_stale_minutes = 5\n") == SMALL
    assert declared_stale_minutes("[idle]\nticks = 16\n") == DECLARED


def test_a_live_loop_with_an_old_tick_is_a_warning(tmp_path: Path) -> None:
    """Live and last ticked four days ago: named, with the stamp."""
    _fleet(tmp_path, {"a": STALE}, {"a": "ok"})
    said = stale_findings(tmp_path, ["a"], NOW)
    assert list(said) == ["a"]
    assert "2026-11-10T18:06:42" in said["a"]


def test_a_live_loop_with_a_fresh_tick_is_not(tmp_path: Path) -> None:
    """MUTANT: the same live repo with a tick fifteen minutes old draws nothing."""
    _fleet(tmp_path, {"a": FRESH}, {"a": "ok"})
    assert stale_findings(tmp_path, ["a"], NOW) == {}


def test_a_peer_line_is_not_a_tick(tmp_path: Path) -> None:
    """A recent peer line leaves the loop with no recent tick: still stale."""
    _fleet(tmp_path, {"a": STALE + PEER}, {"a": "ok"})
    assert list(stale_findings(tmp_path, ["a"], NOW)) == ["a"]


def test_a_live_loop_with_no_tick_line_at_all_is_a_warning(tmp_path: Path) -> None:
    """No tick line is stale too, said as 'at all'."""
    _fleet(tmp_path, {"a": PEER}, {"a": "ok"})
    assert "at all" in stale_findings(tmp_path, ["a"], NOW)["a"]


def test_a_dormant_repo_is_left_alone(tmp_path: Path) -> None:
    """Most repos are dormant on purpose: an old tick with no live loop is no finding."""
    _fleet(tmp_path, {"a": STALE}, {"a": "dormant"})
    assert stale_findings(tmp_path, ["a"], NOW) == {}


def test_a_readable_export_answers_with_no_reason(tmp_path: Path) -> None:
    """The live repos come with an empty reason; an export that says none is live is not blind."""
    _fleet(tmp_path, {"a": STALE}, {"a": "dormant"})
    assert live_repos(tmp_path) == (set(), "")
    (tmp_path / "liveness.json").write_text('{"repos": {"a": {"verdict": "ok"}}}')
    assert live_repos(tmp_path) == ({"a"}, "")


def test_no_liveness_export_is_blind_not_clean(tmp_path: Path) -> None:
    """Without root/liveness.json the answer carries a reason, and the check says it was blind."""
    _fleet(tmp_path, {"a": STALE, "b": STALE}, None)
    live, blind = live_repos(tmp_path)
    assert not live
    assert "no liveness.json" in blind
    said = stale_findings(tmp_path, ["a", "b"], NOW)
    assert list(said) == ["a"]
    assert "liveness export absent: tick staleness not judged" in said["a"]


def test_an_export_that_is_not_json_is_blind_too(tmp_path: Path) -> None:
    """MUTANT: reading a broken export as 'no loop is live' would look exactly like all clear."""
    _fleet(tmp_path, {"a": STALE}, None)
    (tmp_path / "liveness.json").write_text("not json", encoding="utf-8")
    assert live_repos(tmp_path)[1] == "liveness.json is not JSON"
    assert "not judged" in stale_findings(tmp_path, ["a"], NOW)["a"]
