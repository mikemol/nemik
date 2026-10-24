# Which of nemik's ready cards can start, and why the old ones wait (nemik:W930, W929)

The operator observed (2026-10-23) that the page does not show the queue as a queue: the same ready
cards stay ready for ages while new cards come ready. The first question W929 asks is whether the head
of the queue is work that can start. This answers it for nemik's own queue, read on 2026-10-23.

## What was measured

`nemik-check --ready-neither --repo nemik` listed 11 ready cards untouched for longer than the bound
(2.2 days, the p90 of finished small cards): W370 5.1 d, W709 4.8, W714 4.5, W719 4.5, W764 3.6, W768
3.4, W643 3.2, W789 3.1, W750 2.8, W829 2.7, W369 2.5. In the same days about thirty newer cards
were minted and landed. `nemik-starved` listed none, because its bar is 14 days.

## Can each of them start?

I read each card's next step.

| Card | Next step | Can it start now? |
|---|---|---|
| W369, W370 | record a real tracker payload as a fixture, then a typed reader; the delivery needs a token | **Yes**, the first step: a public issue's JSON can be fetched without a token. Only the delivery is the operator's. |
| W709, W714, W764, W768, W789, W829 | code changes with manifests | Yes. |
| W643 | repin to 4704f43 or later, then call the footprint library | Yes: the repin step is done (c9c0070 is later). |
| W750 | ask mtools-ad where an intervention event is read back, then date the changes | Yes: sending the ask is the step. |
| W719 | answer life:W52 with the result of its three children | **No: its children were all done, so it was waiting to be closed.** Closed 2026-10-23 with a letter to life. |

So one of eleven was not workable, and it was an umbrella whose work was finished: the head of the
queue is not clogged by cards that cannot start. This corrects what I said when I raised the card:
I took W369 and W370 for unworkable because their delivery needs a token, and their first steps
do not.

## Why the old ones wait, then

Not misclassification: attention. The loop works what is asked of it and what arrives (a peer's
ask, an operator request, a gate refusal), and the ranking puts the oldest, heaviest cards first on
paper without anything making the session take them. In this stretch the cards that were worked
were mostly asked for. Two things would make that visible and change it, which the page does not do
today and W931 to W933 build: the place of each card in the order with how many newer cards were
ranked ahead of it, and a forecast of when it will be reached, shown only once the forecast has
verified skill (W749).

## What the page shows now (W931 to W933)

W931 serves the order, W932 draws it as a numbered queue with each card's weight, wait and the
newer cards ranked ahead of it, and W933 sets the rule for a start time: **a predicted start is
shown only for a card whose forecast has verified skill over climatology, and is labelled with that
skill.** On 2026-10-24 no forecast has it (W749: the old model scored -8.69 at +1d; the new model's
issue is scored once its horizon has passed, W946), so the Queue section shows the order and the wait
and says in its heading that no start time is shown, and why. A time shown without skill would be a
claim with no grounds. When W749 records a skill above zero, the section may add a time, with the
skill beside it; until then the heading stays.

## What follows

W931 (the queue document), W932 (the Queue panel) and W933 (the forecast, honestly labelled) stand as
carded; W933 is this rule. The fix this measurement points at is not a different mark on a card; it is that the
queue's order is shown and held to.
