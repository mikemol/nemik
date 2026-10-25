# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1025: the round file and the round-drift gauges, written from each repo's round.

roundof (nemik:W1024) draws a repo's round and measures how much of its working set lies outside
it. This writes the two things other tools read: the round file, one line of JSON,
{"as_of", "rows": [{"repo", "symbol", "rank", "salience"}, ...]}, a repo's round cards in rank
order, numbers as quoted text the way the pace file writes them (the one form luthen's egress gate
also rewrites it to, so readers parse a document, never lines); and the Prometheus gauges
nemik_round_size, nemik_round_working, nemik_round_outside and nemik_round_drift per repo (drift is
the share outside over working, 0 when nothing is worked), beside nemik_round_as_of in unix seconds.
Existence of the file is what mtools:W1942's witness reads; its own as_of dates it. No import, so
the Codon census compiles it.
"""

ROUND_FILE = "round.json"
GAUGE_SIZE = "nemik_round_size"
GAUGE_WORKING = "nemik_round_working"
GAUGE_OUTSIDE = "nemik_round_outside"
GAUGE_DRIFT = "nemik_round_drift"
GAUGE_AS_OF = "nemik_round_as_of"

Taken = tuple[str, list[tuple[str, int, str]]]
Stat = tuple[str, int, int, int]


def round_text(as_of: str, rounds: list[Taken]) -> str:
    """Write the round file.

    Args:
        as_of: When the rounds were drawn, a UTC stamp.
        rounds: Each repo with its round cards, each as (symbol, rank from 1, salience text).

    Returns:
        One line of JSON, {"as_of": ..., "rows": [...]}, a row per round card, repos in the order
        given: the form luthen's egress gate rewrites the file to, so a reader parses one document
        whether or not the gate dropped a row.

    """
    rows = [
        f'{{"repo": "{repo}", "symbol": "{symbol}", "rank": "{place}", '
        f'"salience": "{salience}"}}'
        for repo, cards in rounds
        for symbol, place, salience in cards
    ]
    return f'{{"as_of": "{as_of}", "rows": [{", ".join(rows)}]}}\n'


def drift_text(outside: int, working: int) -> str:
    """Write the share of the working set that lies outside the round.

    Returns:
        outside over working to four significant figures; 0 when nothing is worked.

    """
    if working <= 0:
        return "0"
    return f"{outside / working:.4g}"


def metric_lines(stats: list[Stat], as_of_seconds: int) -> list[str]:
    """Write the round gauges, Prometheus text.

    Args:
        stats: (repo, round size, working cards, working cards outside the round) per repo.
        as_of_seconds: When the rounds were drawn, unix seconds.

    Returns:
        A TYPE line and one sample per repo for each gauge, then the gauge that dates them.

    """
    out = [f"# TYPE {GAUGE_SIZE} gauge"]
    out += [f'{GAUGE_SIZE}{{repo="{repo}"}} {size}' for repo, size, _, _ in stats]
    out.append(f"# TYPE {GAUGE_WORKING} gauge")
    out += [f'{GAUGE_WORKING}{{repo="{repo}"}} {work}' for repo, _, work, _ in stats]
    out.append(f"# TYPE {GAUGE_OUTSIDE} gauge")
    out += [f'{GAUGE_OUTSIDE}{{repo="{repo}"}} {away}' for repo, _, _, away in stats]
    out.append(f"# TYPE {GAUGE_DRIFT} gauge")
    out += [
        f'{GAUGE_DRIFT}{{repo="{repo}"}} {drift_text(away, work)}'
        for repo, _, work, away in stats
    ]
    out.append(f"# TYPE {GAUGE_AS_OF} gauge")
    out.append(f"{GAUGE_AS_OF} {as_of_seconds}")
    return out
