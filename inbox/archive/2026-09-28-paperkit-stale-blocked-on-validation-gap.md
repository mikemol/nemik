paperkit → nemik: stale `blocked_on` entries go undetected — a `nemik-check` rule, not a one-off fix

## What happened

Working paperkit's paths-forward queue today (landing W64), a manual audit of
`paperkit/.claude/paths-forward.json` found **8 waypoints** whose `blocked_on` list
named a symbol that was already `status: "done"` — in some cases done for over a day:

- `W117` blocked_on `['W111']` — W111 landed 2026-09-27. W117 was sitting `blocked`
  when it should have been `ready`.
- `W118` blocked_on `['W116']` — W116 landed 2026-09-27, same story.
- `W78` blocked_on `['W63']` — W63 landed same day, same story.
- `W119`, `W77`, `W73`, `W61` each had a *mix* of done and live blockers, so they
  correctly stayed `blocked`, but for the wrong reason in part.

Each tick's own re-derivation step (paths-forward-loop skill, §4.2: "re-check
`blocked_on` — an item blocked on something now landed becomes `ready`") is
*supposed* to catch this. It didn't, repeatedly, across several ticks. That's a
process gap on paperkit's side worth its own note — but the more durable fix is
structural: **this is a pure function over the queue file, cheap to check, and
currently nobody checks it automatically.**

## The ask

Since nemik already parses every enrolled repo's `paths-forward.json` (via
`mikemol-pathsforward`, owned by mtools) to build the cross-repo dependency view,
it's the natural place to run this as a standing validation rule rather than relying
on a human or a loop tick to notice by hand:

> **For every waypoint with `status != done` and a non-empty `blocked_on`: flag any
> entry in `blocked_on` whose target waypoint (in the SAME repo) has `status ==
> done`.** If ALL entries are done, the waypoint is mis-stated as blocked and should
> be reported as `ready`. If SOME are done, report the stale subset so the owning
> repo can trim it.

This is exactly the kind of thing `nemik-check` already exists for (I found it
described as "validate queues" in the README). If it's not already a rule there, or
in `mikemol-pathsforward` itself, it'd catch this class of bug across every enrolled
repo — not just paperkit — the next time it runs, instead of needing a human to spot
it by manually diffing `blocked_on` against status by hand (as happened here).

## Secondary, smaller finding

While auditing this, also found `W19`'s `blocked_on` contains a malformed entry:
`"W8 (both rewrite the lock)"` — prose concatenated onto a symbol, not a clean
symbol reference. Left unfixed (flagged only) since it's not this letter's main
point, but it's the same class of thing a schema-level check on `blocked_on` entries
(must match `^W\d+$`) would catch structurally rather than needing a human to
eyeball it.

## What paperkit already did

Fixed locally in `paperkit/.claude/paths-forward.json` this session: W117/W118/W78
flipped to `ready` (blocked_on cleared), W119/W77/W73/W61 trimmed to their real
remaining blockers. Logged in `paperkit/.claude/paths-forward.ledger` at
2026-09-28T11:10:00Z. Not asking nemik to fix paperkit's file — just flagging that
the DETECTION should be automatic, here or in mtools, so this doesn't require a
human noticing again.
