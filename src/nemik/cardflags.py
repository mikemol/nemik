# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W714: flags blocks.annotate derives, as functions of plain card edges.

blocks.annotate writes derived triples into an rdflib graph. Each flag here is the same derivation
over `repo:W<n>` strings, so it can run where rdflib cannot (the browser port, nemik:W508). The
graph version stays the reference; tests/test_cardflags.py checks the two agree on a fixture queue.
The module imports only `re`, so the Codon census compiles it. Flags so far: allBlockersLanded,
readyBehindOpen, unresolvedBlocker.
"""

import re

CAL_BLOCK = re.compile(r"cal:[a-z][a-z0-9-]{0,31}/\S+")
HOST_BLOCK = re.compile(r"host:[A-Za-z0-9][A-Za-z0-9._@-]*")
WITNESSES = "nemik-witnesses"


def unresolved_blockers(
    cited: dict[str, list[str]],
    resolved: set[str],
    human: set[str],
    witnessed: set[str],
) -> dict[str, list[str]]:
    """Find the blocked_on entries nemik can resolve to no party (the operator's 2026-09-26 defect).

    A blocked card whose blocked_on names nothing nemik can resolve (no workstream, waypoint or
    operator) draws no edge at all. A condition is resolved by its form (cal:<label>/<uid>,
    host:<id>), and `nemik-witnesses` is a party only for a card that has a witness (nemik:W520).

    Args:
        cited: blocked card -> its blocked_on entries, as written.
        resolved: The blocked cards that wait for at least one resolvable card.
        human: The blocked cards whose blocked_kind is human (drawn to an operator lane).
        witnessed: The cards that declare a witness.

    Returns:
        card -> the entries that resolve to no party, for each card that has any.

    """
    out: dict[str, list[str]] = {}
    for card, texts in cited.items():
        if card in resolved or card in human:
            continue
        bad = [
            t
            for t in (x.strip() for x in texts)
            if not (
                CAL_BLOCK.fullmatch(t)
                or HOST_BLOCK.fullmatch(t)
                or (t == WITNESSES and card in witnessed)
            )
        ]
        if bad:
            out[card] = bad
    return out


def all_blockers_landed(
    waits: dict[str, list[str]],
    cited: dict[str, int],
    landed: set[str],
    done: set[str],
) -> set[str]:
    """Find the open cards whose every blocker has already landed (nemik:W110).

    A block on a card that is done, or dropped to residue, is stale: the waiter should have been
    lifted to ready, or its blocked_on trimmed. Only a card that waits on at least one landed card
    and whose blocked_on entries are all of them is flagged.

    Args:
        waits: card -> the cards it waits for, as resolved references.
        cited: card -> how many distinct blocked_on entries it has, resolved or not.
        landed: The cards that are done or dropped.
        done: The cards whose own state is done, which are never flagged.

    Returns:
        The cards that wait on landed cards and on nothing else.

    """
    out: set[str] = set()
    for card, targets in waits.items():
        if card in done:
            continue
        gone = [t for t in targets if t in landed]
        if gone and len(gone) == cited.get(card, 0):
            out.add(card)
    return out


UMBRELLA = 2  # open enablers of its own repo that make a ready card an umbrella


# nemik:W971: the operator-ask category, as blocks._operator_asks decides it. The regexes are
# copied (a Codon module cannot import a sibling) and tests/test_cardflags_asks.py checks the
# two agree.
EXPLICIT = re.compile(r"^\s*operator\s*:\s*(decide|act)\b", re.IGNORECASE)
ACT_ASK = re.compile(r"^\s*operator\s*:\s*act\b", re.IGNORECASE)
ANSWERED = re.compile(
    r"\b(ruled|keep holding|approved|go-ahead given|decided)\b", re.IGNORECASE
)
CONDITION = re.compile(
    r"^\s*(event:|a green tree|once\b|when\b|after\b)|\bresume when\b|\bonce the\b",
    re.IGNORECASE,
)
DECISION = re.compile(
    r"\b(approv\w*|go\b|go-ahead|choice|choose|decide|decision|which|whether|confirm|restart|"
    r"act|acts|teardown|layout|owns|credential|push|commit)\b|\?",
    re.IGNORECASE,
)
BARE = re.compile(
    r"^\s*(the\s+)?(operator|user|mikemol|mike|human)\s*(\(\w+\))?\s*$", re.IGNORECASE
)
COMMAND = re.compile(
    r"\benv\s+-C\s+\S+\s+/\S+\s+-m\s+\S+"
    r"|\bsudo\s+(?:-\S+\s+)*(?:/\S+|env\s+-C\b|systemctl\s+\w|python[\d.]*\s+-m\s+\S)"
)
MACHINE_ACT = re.compile(
    r"\b(sudo|root|run|apply|applies|command|install|systemctl|reaper|restore|drill)\b",
    re.IGNORECASE,
)
TITLE_ASK = re.compile(r"^\s*operator\b[^:]{0,60}:", re.IGNORECASE)
LEAD_WORD = re.compile(r"^\s*(operator|user|mikemol|mike|human)\s*[:(]?", re.IGNORECASE)
LONG_ASK_WORDS = 3
PRIORITY = ("needs-you", "no-command", "unstated", "condition", "answered")


def operator_category(text: str) -> str:
    """Categorise one blocked_on text that waits on the operator (nemik:W971).

    Args:
        text: One blocked_on entry.

    Returns:
        needs-you, no-command (an act on a machine with no command to run), answered, condition,
        or unstated, by the same rules as blocks.operator_category.

    """
    if EXPLICIT.match(text):
        machine = bool(MACHINE_ACT.search(text)) and not COMMAND.search(text)
        return "no-command" if ACT_ASK.match(text) and machine else "needs-you"
    if ANSWERED.search(text):
        return "answered"
    if CONDITION.search(text):
        return "condition"
    if BARE.match(text):
        return "unstated"
    lead = LEAD_WORD.match(text)
    rest = text[lead.end() :] if lead else text
    long_enough = len(rest.split()) >= LONG_ASK_WORDS
    return "needs-you" if DECISION.search(rest) or long_enough else "unstated"


def ask_category(texts: list[str], title: str, repo: str, errands: set[str]) -> str:
    """Categorise a card's ask from all its blocked_on texts (nemik:W971).

    A bare "operator" whose ask is carried in a title that starts `OPERATOR ...:` reads the title;
    the most actionable category across several texts wins; and a no-command ask in an errand repo
    is an errand, the operator's own business.

    Args:
        texts: The card's blocked_on entries.
        title: The card's title.
        repo: The card's repo.
        errands: The repos whose machine-sounding acts are the operator's own errands.

    Returns:
        needs-you, no-command, errand, unstated, condition or answered.

    """
    if texts and all(BARE.match(t) for t in texts) and TITLE_ASK.match(title):
        texts = [title]
    cats = [operator_category(t) for t in texts] or ["unstated"]
    best = next(c for c in PRIORITY if c in cats)
    return "errand" if best == "no-command" and repo in errands else best


def _repo(cite: str) -> str:
    """Name the repo of a `repo:W<n>` reference.

    Returns:
        The part before the colon, or the whole text for a bare repo name.

    """
    return cite.partition(":")[0]


def _by_blocker(row: tuple[str, str, list[str]]) -> str:
    """Sort key for inbound rows: blocker, then waiting card, then claims, as blocks.inbound orders.

    Returns:
        One text that sorts the way the (blocker, card, claims) tuple does.

    """
    sep = chr(0)
    return row[1] + sep + row[0] + sep + sep.join(row[2])


def inbound_rows(
    waits: dict[str, list[str]],
    enablers: dict[str, list[str]],
    informed: dict[str, list[str]],
) -> list[tuple[str, str, list[str]]]:
    """Find each open card's waits on another workstream, with the blocker's claiming cards (W972).

    The same reading as blocks.inbound over plain edges. A wait on a bare repo is claimed by the
    cards of that repo that enable the waiter or were caused by it; a wait on a named card is
    claimed by that card too. A wait on the waiter's own repo is no inbound wait.

    Args:
        waits: open card -> what it waits on: a bare repo name, or a `repo:W<n>` card; the operator
            and targets outside the graph are left out by the caller.
        enablers: card -> the cards that enable it.
        informed: card -> the cards caused by it.

    Returns:
        (waiting card, blocker repo, claiming cards sorted), ordered by blocker, card, claims.

    """
    rows: list[tuple[str, str, list[str]]] = []
    for card, targets in waits.items():
        for target in targets:
            blocker = _repo(target)
            if blocker == _repo(card):
                continue
            claims = {c for c in enablers.get(card, []) if _repo(c) == blocker}
            claims.update(c for c in informed.get(card, []) if _repo(c) == blocker)
            if ":" in target:
                claims.add(target)
            rows.append((card, blocker, sorted(claims)))
    return sorted(rows, key=_by_blocker)


def unclaimed_blocks(
    rows: list[tuple[str, str, list[str]]],
) -> list[tuple[str, str]]:
    """List the inbound waits nothing in the blocker's repo claims (nemik:W972).

    Returns:
        (waiting card, blocker repo) for each row with no claiming card, in the rows' order.

    """
    return [(card, blocker) for card, blocker, claims in rows if not claims]


def ready_behind_open(
    enablers: dict[str, list[str]], ready: set[str], open_cards: set[str]
) -> dict[str, list[str]]:
    """Find the ready cards an open card enables, with those enablers (nemik:W465).

    The flow model already treats such a card as waiting while its fill says ready. Umbrellas (two
    or more open enablers of the card's own repo) are left out: ReadyUmbrellaShape reports them.

    Args:
        enablers: card -> the cards that enable it, as `repo:W<n>` references.
        ready: The cards whose state is ready.
        open_cards: The cards that exist and are not done.

    Returns:
        card -> its open enablers, sorted, for each ready card that has any and is no umbrella.

    """
    out: dict[str, list[str]] = {}
    for card in sorted(ready):
        held = [c for c in enablers.get(card, []) if c in open_cards]
        own = [c for c in held if c.partition(":")[0] == card.partition(":")[0]]
        if held and len(own) < UMBRELLA:
            out[card] = sorted(held)
    return out
