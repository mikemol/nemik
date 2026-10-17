# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W634: per-repo exports decide what the fleet withholds, failing closed per repo."""

import json
from pathlib import Path

from nemik.exportwire import repo_symbols, withheld_by_exports

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_the_fixture_fleet_has_cards_to_withhold() -> None:
    """The fixture queues hold card symbols; the tests below depend on it."""
    symbols = repo_symbols(FLEET)
    assert symbols
    assert any(symbols.values())


def test_no_exports_withholds_every_card_of_every_repo(tmp_path: Path) -> None:
    """An empty exports directory publishes nothing: each repo fails closed."""
    withheld = withheld_by_exports(FLEET, tmp_path)
    everything = {
        f"{repo}:{s}" for repo, symbols in repo_symbols(FLEET).items() for s in symbols
    }
    assert withheld == everything


def test_a_repos_own_export_releases_the_cards_it_publishes(tmp_path: Path) -> None:
    """One repo's export that publishes all of its cards leaves only the other repos withheld."""
    symbols = repo_symbols(FLEET)
    repo = next(r for r, s in symbols.items() if s)
    export = {
        "version": 2,
        "repo": repo,
        "cards": [{"symbol": s} for s in symbols[repo]],
        "withheld": [],
    }
    (tmp_path / f"{repo}.json").write_text(json.dumps(export), encoding="utf-8")
    withheld = withheld_by_exports(FLEET, tmp_path)
    assert not {r for r in withheld if r.startswith(f"{repo}:")}
    others = {f"{r}:{s}" for r, ss in symbols.items() if r != repo for s in ss}
    assert withheld == others
