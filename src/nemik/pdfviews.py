# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""pdfviews: the named views nemik-pdf prints, as steps on the page's header controls (nemik:W892).

The page keeps no view in its URL, so a view is only reachable by setting its controls (the table
in docs/pdf-views.md, W891). This holds each view as a list of steps, and no browser: pure data and
one function, so what a view means is testable without Chromium and compiles under Codon.
"""

# (action, selector, value): action is check, click or select; value is the option for select
Step = tuple[str, str, str]

FLEET = "fleet"
TREEMAP = "treemap"
REPO = "repo"
ASKS = "asks"
RANK = "rank"
NAMES = [FLEET, TREEMAP, REPO, ASKS, RANK]
HOPS = "2"


def _order(value: str) -> Step:
    """Pick one of the card list's orders.

    Returns:
        The step that checks that order's radio.

    """
    return ("check", f'input[name="listmode"][value="{value}"]', "")


def steps(view: str, repo: str = "") -> list[Step]:
    """List the control settings that reach a view from the page's defaults.

    Args:
        view: One of NAMES.
        repo: The repo to show; required for the repo view and ignored by the others.

    Returns:
        The steps, in the order to apply them.

    Raises:
        ValueError: when the view is unknown, or the repo view is asked for without a repo.

    """
    if view == FLEET:
        return [("check", "#rollup", "")]
    if view == TREEMAP:
        return [("check", "#treemap", "")]
    if view == REPO:
        if not repo:
            msg = "the repo view needs a repo"
            raise ValueError(msg)
        return [
            ("click", f'#repos button[data-repo="{repo}"]', ""),
            ("select", "#depth", HOPS),
        ]
    if view in {ASKS, RANK}:
        return [_order(view)]
    msg = f"unknown view {view!r}; one of {', '.join(NAMES)}"
    raise ValueError(msg)
