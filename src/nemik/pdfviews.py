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
# nemik:W955: the page now reads its address (W953), so a view can also be reached by opening
# the page at one: `address` sets no control, the address does the picking, and it is not one
# of NAMES (those are settings of controls).
ADDRESS = "address"
HOPS = "2"


def at(url: str, address: str) -> str:
    """Join a page URL to an address the page reads on load.

    Args:
        url: The running nemik-serve, with or without a fragment.
        address: `#/<repo>[/W<n>]`, as nemik.web's viewstate writes it.

    Returns:
        The URL with that fragment in place of any other.

    Raises:
        ValueError: when the address does not start with `#/`.

    """
    if not address.startswith("#/"):
        msg = f"an address starts with #/ (for example #/mtools/W5), not {address!r}"
        raise ValueError(msg)
    return url.partition("#")[0] + address


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
    if view == ADDRESS:
        return []
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
