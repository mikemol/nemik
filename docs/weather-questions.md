# The weather and climate series: the questions first

nemik:W743. The operator's rulings (2026-10-19, host session 695f3e0a, both warranted on W743):
track event histories for each change to a card, as weather and climate (repos are regions, cards
are stations), and "engineer the information source to contain the information required for the
question to be had", the converse of minding the Shannon limit: a conclusion cannot carry more
information than the measurement it came from, so the measurement is built to carry what the
questions need. So the questions come first, and each is checked against the bits the source
holds.

## The questions (the umbrella's acceptance list)

The operator's four:

1. **What does our forecast read?** For a card, the probability it is done by +1 d, +3 d, +7 d;
   for a repo, the expected done count and frontier size at each lead.
2. **How does the forecast line up over time?** Each forecast scored when its target passes
   (Brier and reliability by lead, MAE for counts) against persistence and climatology.
3. **How do we improve the forecast?** Add one feature at a time and keep it only if verified
   skill over climatology rises.
4. **How do we improve the climate?** Date each practice change as an intervention and measure
   the shift in a before and after window.

Derived from them:

5. **Lead time from ready to done** (and from issued to done), as a distribution per repo.
6. **Reopen rate:** cards that left done, and churn (cards that change status often).
7. **Which intervention moved the climate**, and by how much.
8. **Which cards sit in a state longer than their repo's usual** (the stall reading).

## The bits each question needs, and where they are

| Need | Question | Source today | Gap |
|---|---|---|---|
| The prior state on every transition (from and to) | 5, 6, 8 | nemik W744 events carry `from` and `to` per field; mtools W1731 carries old and new | none for later changes. **A card's first values:** W744 emits only "minted" when a card first appears, not its starting status, blockers or size, so a card never changed since its first commit reads empty. Fix in W744; W1731 must emit one event per initial field on an add |
| When it happened | all | W744: the commit time (a floor: a flip between two commits is invisible). W1731: the OTLP record's own timestamp | W1731 should name the clock: UTC, millisecond, the writer's own |
| Which command made the change (the mechanism) | 6, 7 | the ledger names mechanism per tick; W744 has none | W1731 should carry `via`: the writer flag (`--update`, `--add`, `--update-many`, `--prune-landed`, `--tick-close`, an automatic prune or bump) |
| Who: the session, and whether a human or an agent | 7 | W1731: session. Not in W744 | add `actor`: operator, agent or automation (the writer knows `minted_during` and the tick lock holder) |
| Which changes belong to one command | 5, 6 | neither | W1731 should carry a `mutation` id shared by the field events of one command, so one `--update` with three fields is one change, not three |
| The size of the card's plan, over time | 3 | `manifest` and `size_class` are fields of the queue | W1731 must emit them (and `weight`, `touches`, `witness`) as tracked fields; W744's tracked set is status, blocked_kind, blocked_on and enables, so it must grow to match |
| The big text fields | 3 | evidence and next step are half the bytes of a queue | W1731 should carry their length and a hash, not their text: the bits a forecast needs are that they changed and by how much |
| When a card landed, as against when it was marked done | 5 | the queue's `completed` stamp; the commit's Waypoint trailer | a landing event from `mikemol-commit`: card, sha, gate seconds and verdict class (the trend reader mtools W1718 to W1721 has these) |
| Interventions as events | 4, 7 | none: atomizing, stacking, sharding and repinning are practices, not card changes | an event kind with no card: a station `fleet:intervention`, a kind and a note, written by a writer mode (`--mark`) or by a commit trailer. Needs an owner: mtools |
| Every forecast kept, with its issue time and lead | 1, 2 | not yet built (nemik W747) | the shingle is append-only by design: each issue stores the features it read, so a later verification can rebuild the question it answered |
| The climate at issue time, for the baselines | 2 | derivable from the events up to that time | W746 must be a function of (events, time), not of the live queue |

## The resolution floor: what the sampling rate allows

The operator's second ruling (2026-10-19, record 86072, warranted on W743): ensure the sampling
rate is sufficient for the resolution desired, and be mindful of the boundaries the sampling rate
of the data at hand imposes. Two sources feed the series, and they sample differently:

- **Backfilled history is commit-grain.** The sample is a commit of the queue file. Every
  mutation between two commits collapses into one diff, so a round trip inside a commit (ready,
  working, ready) is invisible, and every timestamp is the commit's time, not the mutation's.
  The queue is committed far less often than it is written (nemik 12 commits a day, but mtools
  44 hours between two; three repos never; `docs/status-history-survey.md`).
- **The live feed is mutation-grain**, once mtools:W1731 lands. Until then there is no finer
  source.

So backfilled events carry a `grain` of `commit`, and the live ones `mutation`. What each
question can claim, at commit grain:

| Question | At commit grain | Floor |
|---|---|---|
| Forecast read (1) | a probability for a lead is fine; it is a forecast, not an observation | none |
| Lining up over time (2) | the truth a forecast is scored against is the commit's | do not score at a lead shorter than the repo's typical commit gap; per repo, that gap is the floor (`nemik-history --density`) |
| Improve the forecast (3) | features are read at commit times | a feature that changes faster than the grain cannot be tested |
| Improve the climate (4, 7) | an intervention is seen in a window of at least a few commits | before and after windows no shorter than several commit gaps |
| Lead time ready to done (5) | the ready and done instants are the commits that first show them | understated or overstated by up to one gap each; report the gap beside the figure |
| Reopen rate (6) | a done card that reopens and closes again inside one commit is invisible | a lower bound |
| Time in working, stalls (8) | time in a state is measured between commits | a lower bound; a state shorter than the gap is not seen |

A figure computed from the backfill states its grain, and W748 refuses to score a forecast
whose lead is below the grain of the truth it would be scored against.

## What this asks of each owner

- **nemik** (this repo): W744 emits a card's starting values on a mint, and grows its tracked
  fields to cover manifest, size and the rest; W745 to W750 are built on the grown set.
- **mtools** (W1731 and a landing and intervention emitter): the missing fields above, before
  W1731 is built.
- **luthen** stores the series and draws the board; nothing here changes for them except the
  field names.
