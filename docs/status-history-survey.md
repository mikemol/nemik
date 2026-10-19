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

With the ledger's lines a day beside it (W741, the same `--density` mode):

| Repo | Commits | Per day | Longest gap | Ledger lines a day |
|---|---|---|---|---|
| mtools | 80 | 11.4 | 44.4 h | 185.7 |
| luthen-observability | 47 | 6.7 | 49.9 h | 144.6 |
| nemik | 84 | 12.0 | 14.5 h | 62.3 |
| el-openglo | 64 | 9.1 | 56.4 h | 54.9 |
| amr-skills | 32 | 4.6 | 76.9 h | 13.7 |
| summit | 43 | 6.1 | 2.5 h | 4.9 |
| linux-sources | 36 | 5.1 | 71.9 h | 5.7 |
| gcalculus | 9 | 1.3 | 81.2 h | 7.1 |
| life | 4 | 0.6 | 116.6 h | 0.7 |
| aeternum | 2 | 0.3 | 21.1 h | 0.3 |
| resumes | 1 | 0.1 | n/a | 0.4 |
| gabion | 0 | 0.0 | n/a | 32.1 |
| paperkit | 0 | 0.0 | n/a | 28.4 |
| github | 0 | 0.0 | n/a | 11.4 |
| substrate | 0 | 0.0 | n/a | 0.4 |
| rosettapkg | 0 | 0.0 | n/a | 0.3 |

The longest gap is measured between commits inside the window, so a repo that has been quiet
since its last commit shows no gap for that quiet time. Read it as: in the busiest repos
(nemik, mtools, el-openglo, luthen-observability, summit) a transition is seen within a day or
two; in the quieter ones (gcalculus, life) a card can change status and the git stream shows
nothing for four to five days. Five repos committed no queue change in the week.

## What the ledger column shows

- **Three repos have an active ledger and no queue-file commit at all** in the week: gabion
  (32 lines a day), paperkit (28) and github (11). Their status changes are invisible to the
  git stream; for them the ledger is the only history. Why their queue is never committed (an
  untracked file, or a repo that does not commit it) was not looked into here.
- **A ledger line is a tick, not a status transition.** It names the card, the outcome and
  the mechanism, so it says a card was worked and how, not which status it moved between. It
  fills the "when was this card touched" gap, not the "what did it change from and to" one.
- **Quiet in both:** life, aeternum, resumes, substrate and rosettapkg write under one ledger
  line a day, so little changes there to miss.

## Not measured, so open

- The forge feed and OTLP streams.
- Why gabion, paperkit and github never commit their queue file.

## Verdict

No writer change to mtools is justified yet. The git snapshots give every committed transition
for the busy repos. The ledger covers the uncommitted intervals as "touched at", which is
enough to date a card's activity but not to rebuild its status path. A hole remains for the
three repos whose queue is never committed: if a status path is wanted for them, the cheapest
change is for them to commit their queue file, not a new stream.
