# Luthen's loop and token series, and what nemik builds on them

nemik:W352 (liveness board) and nemik:W353 (token cost per card) wait on series that luthen-observability now
publishes every minute (luthen:W1099; read back through its query API on 2026-10-18 00:48 EDT, 34 series pushed).
This note records the series as luthen described them, the two derived views, and what is still unknown, so the
build starts from a stated contract.

## The series (stored names are dotted, as for all OTLP in this fleet)

| series | labels | value |
|---|---|---|
| `luthen.claude.loop.liveness` | `repo`, `verdict` | 1 for each repo's current verdict (values from `checks.loop_liveness`) |
| `luthen.claude.loop.last.tick.timestamp.seconds` | `repo` | the repo's last tick as epoch seconds; absent, never 0, when the ledger has no parseable tick |
| `luthen.claude.session.tokens.total` | `repo`, `session`, `kind` | cumulative tokens since the session began; `kind` is input, output, cache_create or cache_read; `session` is the transcript's UUID |

Bounds luthen states: only the newest 50 transcripts are read, and a session appears once its transcript is fully
read, so a session can be missing for its first runs (the first full catch-up is some tens of runs).

## W352: awake, idle, asleep against ready cards

A repo's state is luthen's verdict, read the way `nemik.wake` already reads `loop_liveness`: **awake** for `ok`
(a live session ticking), **asleep** for `dormant` (no live session), **idle** for anything else (`stale` today, and
any verdict luthen adds later is shown as it comes, not refused). nemik does not detect liveness itself, so the
tick's age is not used to decide a state (an earlier draft did, and disagreed with `wake`). The board joins that
state, over time through the snapshot's history rows, with nemik's ready count from the queue graph, so "which repos
had workable cards while not awake" is `luthenseries.stranded` (asleep ones first), a query over the product of
the two sources and not a new measurement.

## W353: tokens per card

A ledger line carries the tick's time and the card's symbol but no session id today (mtools holds the ledger
grammar). Without one, tokens can be attributed to a repo and a time window, not to a card. Two routes: ask mtools
for a session field on the ledger line, so a line joins `session.tokens.total` exactly; or attribute by window
(the tokens a repo's sessions spent between two ledger lines of one card), which is an estimate that overcounts
when two cards share a tick. The first is exact and the second is available now. The design takes the second as
a labelled estimate until the first exists.

## Still unknown (asked of luthen, not assumed)

- How nemik reads the series: from the pod (the query API's address and any credential it needs) or from a host
  job that writes a file into the export. nemik is read-only and carries no key material, so a credentialed read
  is not the pod's.
- Retention of the minute series, which bounds how far back the board can look.
