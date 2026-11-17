# The cross-repo wait SLO, learned (nemik:W700)

A card that waits on another repo's card is a **cross-repo wait**. How long is too long? The answer
is not a number someone typed. It is learned from the waits themselves, the way W489 learns that 9
in 10 small cards finish within a bound.

## What is learned

`src/nemik/waitslo.py` holds two pure functions over rows of `(age in days, answered)`:

- `target_age(rows, budget)`: the earliest age at which a **Kaplan-Meier** estimate of the share
  still waiting falls to the budget (default 0.1, so 9 in 10 are answered within the target). A wait
  still open is **censored**: it is at least that old and may be far older. When the open waits keep
  the estimate above the budget there is no target to state and the function returns `-1.0`; that is
  the finding, not a gap.
- `burn(rows, target, budget)`: the share of the open waits older than the target, divided by the
  budget. `1.0` spends the budget exactly, `6.0` six times over. `0.0` when nothing is open, and
  `-1.0` (never `0.0`) when no target was learned: the open waits are what kept it from being
  learned, so it must not read as a quiet queue.

## Why not the percentile of answered waits

The answered waits alone are **right-censored**: a wait that is never answered never enters them.
Their 90th percentile therefore understates the true wait. The numbers below show how far.

## What was read (2026-11-17, one time, read-only)

`nemik-history --all --from 2026-09-20 --events` over every repo's committed queue history, pairing
each cross-repo blocker's first appearance on a card with its disappearance (a cite that leaves and
returns counts as a new wait; a wait on a card whose last status event was done, dropped or landed
is not counted as open):

| | waits | age |
|---|---|---|
| answered, both ends seen | 506 | median 0.43 d, p90 9.11 d, max 50.4 d |
| answered within 6 h / 12 h / 1 d / 2 d / 7 d | | 44% / 52% / 56% / 65% / 82% |
| still open | 201 | median 18.2 d |
| open and older than the answered p90 (9.11 d) | 121 | 60% of the open waits |

Against a target of "9 in 10 answered within 9.11 d" the open set spends a 10 percent budget at
**6.0x**. Counting the open waits as censored, as `target_age` does, pushes the learned target far
past 9.11 d, or leaves it unlearnable: the figure above is the *floor* of the problem.

## What is not done

- The band in `salience.py` (a priority band above ordinary work, from the budget's burn) and a
  gauge are not built; `waitslo` has no caller yet.
- The figures are one reading, not a series.
- Other repos' queue histories are read through `nemik-history`, which reads their committed queue
  files from git: recorded debt, not a sibling path read from a working tree.
