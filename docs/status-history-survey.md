# Status history from the streams that already exist

nemik:W582. The question: can the transitions of a card (blocked to ready, minted, done) be
rebuilt from audit streams the fleet already has, without a new ledger format? The operator's
ruling (2026-10-16): use existing machinery and the standards already woven together, not a
bespoke ledger change.

## The stream that exists today: git history of each queue file

Every commit of a repo's `.claude/paths-forward.json` is a state snapshot, and diffing two of
them gives the transitions between. `nemik-history` already does this: `--weekly` (opened,
closed, blocked share, oldest block per ISO week), `--time-in-state` and `--baseline`.

## How dense the stream is (coverage)

`nemik-history --churn --all`, 2026-10-12 to 2026-10-19, 16 repos:

- 481 commits touched a queue file: about 69 a day across the fleet, 4.3 per repo per day on
  average. The per-repo spread is not measured (see below).
- What a commit did: 12% changed attributes only, 3% flipped a status, 84% changed the
  structure (a card minted, dropped or an edge changed).

Reading: a transition is visible when it is committed. The history is **a floor** (the tool
says so): a status that flipped and flipped back between two commits leaves no trace, and the
live queue is edited far more often than it is committed (mtools-ad: a queue can stay
uncommitted for hours). So the git stream answers "when did this card first appear as blocked
or done in a commit", not "when did it happen".

## What it cannot see, and what could fill the hole

- **Uncommitted intervals.** The ledger (`.claude/paths-forward.ledger`) records ticks with
  outcomes and is written live; it is the existing stream for what the git snapshots miss.
  Mapping a ledger line onto a `prov:Activity` is W530's territory and needs no new format.
- **The forge's activity feed and OTLP records** (W579) are the other streams the card names;
  neither was read here.

## Not measured, so open

- Per-repo density and the gaps between commits (a repo that commits its queue once a day
  hides most of its transitions). `nemik-history` has no mode that prints this; the tool should
  gain one (`--density`: commits per day per repo and the longest gap), not a shell loop over
  `git log`. Carded as W739.
- The forge feed and OTLP streams.

## Verdict so far

No writer change to mtools is justified yet: the git snapshots already give every committed
transition and the ledger covers the live ones. The hole to measure first is the per-repo
commit gap.
