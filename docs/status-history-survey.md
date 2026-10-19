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

## Per-repo density (`nemik-history --density --all`, last 7 days, 2026-10-19)

| Repo | Commits | Per day | Longest gap |
|---|---|---|---|
| nemik | 84 | 12.0 | 14.5 h |
| mtools | 80 | 11.4 | 44.4 h |
| el-openglo | 64 | 9.1 | 56.4 h |
| luthen-observability | 47 | 6.7 | 49.9 h |
| summit | 43 | 6.1 | 2.5 h |
| linux-sources | 36 | 5.1 | 71.9 h |
| amr-skills | 32 | 4.6 | 76.9 h |
| gcalculus | 9 | 1.3 | 81.2 h |
| life | 4 | 0.6 | 116.6 h |
| aeternum | 2 | 0.3 | 21.1 h |
| resumes | 1 | 0.1 | n/a |
| gabion, github, paperkit, rosettapkg, substrate | 0 | 0.0 | n/a |

The longest gap is measured between commits inside the window, so a repo that has been quiet
since its last commit shows no gap for that quiet time. Read it as: in the busiest repos
(nemik, mtools, el-openglo, luthen-observability, summit) a transition is seen within a day or
two; in the quieter ones (gcalculus, life) a card can change status and the git stream shows
nothing for four to five days. Five repos committed no queue change in the week.

## Not measured, so open

- The forge feed and OTLP streams.
- Whether the ledger covers the gap in the quiet repos: the ledger is written live, but this
  survey did not count its lines per repo.

## Verdict

No writer change to mtools is justified: the git snapshots give every committed transition for
the busy repos, and the ledger is the stream that covers what a quiet repo's snapshots miss.
What remains is a count of ledger lines per repo against the git gaps, which decides whether
the quiet repos have a hole.
