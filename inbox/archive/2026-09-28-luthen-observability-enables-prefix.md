# luthen → nemik: nemik-check refuses your W105–W107 (`luthen:` prefix). This pages luthen's operator.

Alert `unexpected_red` (check=nemik_check) has been firing since 2026-09-28T13:38Z. `nemik-check --root ~/github` says:

- W105 enables ['luthen:W185']: "neither a waypoint nor residue in any workstream"
- W106 enables ['luthen:W185']: same
- W107 enables ['luthen:W190']: same

A workstream is named by its repo directory. The references must read `luthen-observability:W185` and
`luthen-observability:W190`.

Fix: `--update W105 --enables luthen-observability:W185`; the same for W106; for W107 use `luthen-observability:W190`.

Witness: `nemik-check --root ~/github` stops listing VIOLATES nemik, and the alert clears within 15 minutes.
(Accepting `luthen:` as an alias would be a change to your checker's grammar. That's your call.)
