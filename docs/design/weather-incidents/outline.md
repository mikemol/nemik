# Weather, incidents and follow-up: the card model (outline)

2026-11-13 · github-cb · Status: outline (skeleton only)

## 1. Problem
- An alert that keeps firing leaves no durable record, so it can be forgotten.
- Weather (outages) shares the W namespace with work, which muddles scheduling.
- Follow-up after an incident competes with new work and loses.
- Sessions wait on cron and watchdog ticks instead of on events.
- Motivating case: the k3s/drum outage of 2026-11-13.

## 2. Goals and non-goals
- Goals: every episode leaves a card; cleanup outranks new debt by construction; one commander per incident; event-driven wake-ups.
- Non-goals: paging the operator for routine episodes; a third oversight loop; hand-typed thresholds.

## 3. Prior art
- **ITIL:** incident vs problem record.
- **IMAG:** declared incident, mitigation first, postmortem with action items that take priority.
- **ICS:** single command, transfer of command, unified command, an action plan per operational period, activity log (ICS-214), demobilization, span of control.
- **Prometheus/Alertmanager:** alert rule (the class) vs alert instance (fingerprint).
- **nemik weather:** a monotone, witness-closed outage card.

## 4. Card model
- **4.1 Namespaces:** W for work, R for reviews, A for weather. A declared table, each namespace with its own monotone counter, and symbols never reused (mtools:W2410).
- **4.2 A-card (weather episode / incident):** one per episode; its Rego witness is mitigation; never reopened; a re-fire mints a new A-card that cites the previous one; a `declared` field.
- **4.3 Umbrella W (problem / postmortem):** one per condition or alert rule; only for declared incidents; its children are the action items.
- **4.4 Driver:** the card whose change caused, or keeps causing, the weather.

## 5. Edges and ranking
- The driver is blocked on the A-card and on the umbrella W.
- Action items are children of the umbrella.
- The ranking consequence: cleanup and follow-up outrank new debt (nemik:W2166).
- While the cause is UNKNOWN there is no driver edge; a fix is unknown until its cause is named.

## 6. Lifecycle
- Fire → mint A → (declare?) → command assigned → mitigate (witness) → A closes (demobilize) → postmortem → action items → umbrella closes → driver unblocked.
- Re-fire: a new A-card linked to the same umbrella.

## 7. Declaration (operator-approved 2026-11-13)
- A stated rule over alert labels and duration; learned baselines, never typed thresholds.
- Undeclared episodes keep their A-cards for recurrence history.
- Recurrence can promote a condition to declared.

## 8. Roles (ICS/IMAG mapped to the fleet)
- Incident commander = the owning session (the host while there is no owner); transfer of command is recorded on the card.
- Unified command when an incident spans owners.
- Dispatcher = luthen's alert monitor.
- Operator = supervisor, not oncall.
- Span of control: a bounded number of open A-cards per commander, surfaced by nemik.
- Incident action plan = the A-card's next_bounded_step; activity log = its ledger.

## 9. Event-driven waiting
- In-session: a Monitor until-loop on the live condition.
- Across sessions: Rego witnesses evaluated by nemik-witnesses.
- Watchdogs (45 min) are a backstop only.
- Later: owner routing, where a live owning session's monitor fires instead of luthen's.

## 10. Producers and signals
- Alert transitions (vmalert/Alertmanager), deduped by fingerprint (luthen W2609).
- Truthful signals: the held-execs count must come from a root producer (W2600).
- btrfs, btrbk and bees panels and forecasts (W2602–W2608).

## 11. Components and owners
- mtools:W2410: writer namespaces.
- nemik:W2166: reader, rank, witnesses, operator view.
- luthen-observability:W2609: alert monitor, A-card minting, umbrella lookup.
- mtools:W2409: the fleet census of tick-waits.

## 12. Migration
- Existing weather cards keep their W symbols; no aliases.
- New weather is A only.
- Retro-fit the k3s outage as the first worked example.

## 13. Worked example: the k3s/drum outage, 2026-11-13
- The A-card: the outage, mitigated about 11:56Z.
- The umbrella: the postmortem, with W2593–W2601 as action items.
- The driver: the W2564 re-land, blocked on both.
- Gaps the model exposes:
  - the activity log is scattered;
  - command was implicit;
  - the gate deadlocked (W2595);
  - the session /proc scan was blind to root tasks.

## 14. Open questions and residue
- Where the namespace table lives and its format.
- Whether the span-of-control limit is learned or fixed.
- What closes an umbrella with no action items.
- How owner routing interacts with unified command.
- Whether the loop prompt changes (operator: "not yet").

## 15. Measures and witnesses
- Time from fire to A-card; time from mitigation to umbrella close.
- Open action items by age.
- A rank-inversion check: a driver ranked above its own follow-up.
