life → nemik: ask — take the operator's calendars as a source

## Why

nemik already shows who is working on what and what is blocked on the operator
(`nemik-operator`, `nemik-wake`). What it cannot show is **when the operator is available**, or
when a waypoint has a hard date on the operator's calendar. Right now life has
`life:W9`, "First aid/CPR/AED training — scheduled", and its date lives only in Google Calendar.
Operator's ruling 2026-09-28: calendar access goes through nemik's infra and mtools' readers,
not a one-off in life.

## What "done" looks like

- A calendars row in README §Sources: `~/.config/nemik/calendars.toml` (outside every repo,
  since it holds credentials), read through mtools' calendar reader (requested in
  mtools/inbox/2026-09-28-life-ask-calendar-reader.md). nemik does not parse `.ics` itself, which
  is the same rule nemik already follows with pathsforward.
- Events become typed nodes, and a waypoint can cite one, e.g. an `at` field in the form
  `cal:<label>/<uid>`, so `life:W9` carries its real date.
- `nemik-operator` shows the operator's next N days of commitments next to the blocks waiting on
  them. That is where "needs-you" meets "you're busy Tuesday".
- `/calendar` or a column on `/wake`. Optional.

⚑ The secret iCal URLs are credentials. They must never be copied into `/graph.json`,
`/graph.ttl`, `/metrics`, the Containerfile export, or error text. The README's hosting note
already mounts only the flat queue export, and this should stay outside that export too.

Depends on mtools' reader. Tracked as `life:W13`.

## Addendum, same day

The preferred upstream is Akonadi on luthen, which luthen-observability has been asked to
declare. The credential then stays in KWallet, and `calendars.toml` names Akonadi collections,
not secret URLs. The rest of this ask is unchanged.
