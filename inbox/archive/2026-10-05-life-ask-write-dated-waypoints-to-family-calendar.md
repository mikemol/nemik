# Ask: write dated waypoints to one Akonadi calendar (read-write)

From life (operator's personal-ops repo), 2026-10-05.

Operator decision: the operator's spouse may see everything the operator knows, so dated life
waypoints should appear on the shared Google calendar **"Mol Family Calendar"**, where the
spouse already looks.

Ask of nemik (with mtools for the writer, if it owns the Akonadi/ICS reader):

1. A **write path** to a named, opted-in calendar in `~/.config/nemik/calendars.toml`, e.g. a
   per-calendar `write = true` (default false), so the read-only guarantee stays the default.
2. Source: waypoints that carry DTSTART/DUE (and their alarms) as VEVENT/VTODO, upserted by a
   stable UID derived from `<repo>:W<n>`, so a republish updates rather than duplicates, and a
   completed or dropped waypoint is removed or marked done.
3. Scope control: which repos/waypoints are mirrored is opted in by the operator, not implied.
4. The Akonadi Google resource is currently authorized read-only; say what authorization change
   the operator has to make, if any.

life will cite the answering waypoint as `--enables`. Nothing here depends on content: this letter
carries process only.
