# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1138: one series per open card, so a card's age is a query and not a new producer.

The exporter published aggregates (nemik_ready_cards{repo}, wait counts), so every new question
about the cards needed a new producer, and Grafana could not ask "ready by repo and age" because no
series carried an age (operator, host 695f3e0a line 104053: the data is flattened or de-enriched
before Grafana can get at it). This publishes the card record un-flattened and leaves the
aggregation to the query:

    nemik_card_issued_seconds{repo, card, status}       when the card was issued, unix seconds
    nemik_card_last_worked_seconds{repo, card}          when it was last worked, unix seconds

Low-churn fields as labels, never a title or any free text: the egress rules keep withheld cards
out, and a withheld card reaches this as a stub with no state of an open card. Plain strings and
integers only, no import beyond one, so the Codon census compiles it.
"""

from nemik.pacepublish import epoch_seconds

GAUGE_ISSUED = "nemik_card_issued_seconds"
GAUGE_WORKED = "nemik_card_last_worked_seconds"
OPEN = ("ready", "working", "blocked")


def _seconds(stamp: str) -> int:
    """Read an ISO stamp as unix seconds.

    Returns:
        The seconds; -1 when the stamp is empty or not a UTC stamp.

    """
    try:
        return epoch_seconds(stamp)
    except ValueError:
        return -1


def card_lines(nodes: list[dict[str, str]]) -> list[str]:
    """Write the per-card series for the open cards of a graph document.

    Args:
        nodes: The graph document's nodes, each with repo, symbol, state, issued and last_worked.

    Returns:
        A TYPE line and one issued sample per open card with a readable issued stamp, then a TYPE
        line and one last-worked sample per open card that has been worked; sorted by repo and
        symbol. Done, dropped, withheld and any node without a repo or symbol are left out.

    """
    open_cards = sorted(
        (
            n["repo"],
            n["symbol"],
            n["state"],
            n.get("issued", ""),
            n.get("last_worked", ""),
        )
        for n in nodes
        if n.get("state", "") in OPEN and n.get("repo", "") and n.get("symbol", "")
    )
    issued = [f"# TYPE {GAUGE_ISSUED} gauge"]
    worked = [f"# TYPE {GAUGE_WORKED} gauge"]
    for repo, symbol, state, born, touched in open_cards:
        at = _seconds(born)
        if at >= 0:
            issued.append(
                f'{GAUGE_ISSUED}{{repo="{repo}",card="{symbol}",status="{state}"}} {at}'
            )
        last = _seconds(touched)
        if last >= 0:
            worked.append(f'{GAUGE_WORKED}{{repo="{repo}",card="{symbol}"}} {last}')
    return [*issued, *worked]
