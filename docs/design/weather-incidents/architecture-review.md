# Weather, Incidents, and Follow-up in Nemik

## Architecture review, prior-art crosswalk, graph semantics, and implementation guidance

**Prepared:** 2026-11-13\
**Basis:** The supplied `weather-incident-card-model-outline.md`, the
prior Nemik architecture discussion and repository survey described in
the conversation, and the external standards and practice references
listed at the end.

------------------------------------------------------------------------

## 1. Executive assessment

The proposal is directionally strong. It identifies a real modeling gap:
a recurring operational condition is not the same thing as a work item,
and neither is the same thing as the retrospective assurance that the
condition has been understood and prevented from recurring.

The cleanest organizing model is:

-   **A --- operational occurrence:** one immutable episode of
    weather/incident.
-   **W --- corrective obligation:** durable work to understand, repair,
    or otherwise disposition the persistent condition.
-   **R --- retrospective assurance:** evidence-backed review of what
    happened, what was learned, and whether resulting controls and
    actions reached an adequate fixed point.

The essential distinctions are:

`Detection != Declaration != Mitigation != Recovery != Remediation != Verification`

These are not merely different labels for one lifecycle. They have
different identities, owners, evidence, and closure conditions. Each
must be constructible, behaviorally reachable, observable, and coverable
by tests. If the system cannot represent and exercise a distinction, it
should not pretend that the distinction exists at runtime.

**Recommendation: advance the proposal, but tighten the identity model,
lifecycle semantics, causal edges, command-transfer protocol, and
event-delivery contract before implementation.** Do not implement this
as ordinary W cards with an `A` prefix. Make A a distinct resource type
and lifecycle, reuse the existing W dependency/umbrella machinery, and
connect it to the existing R retrospective model rather than inventing a
second postmortem subsystem.

The proposal's most important architectural contribution is not a new
incident-management methodology. ITIL, Google SRE/IMAG, and ICS already
provide much of the operational vocabulary. The contribution is to make
their useful distinctions explicit in Nemik's ledger and graph, then
make evidence and dependency topology enforce the follow-up.

## 2. The problem the outline identifies

The outline names five related failures:

1.  An alert that keeps firing can leave no durable record of each
    episode, so an operational event can be forgotten.
2.  Weather/outage records share the W namespace with work, conflating
    operational scheduling with corrective work.
3.  Post-incident follow-up competes with new work and can lose
    priority.
4.  Sessions wait for cron/watchdog ticks instead of waking on relevant
    events.
5.  The k3s/drum outage of 2026-11-13 provides a concrete worked example
    exposing these weaknesses.

These are not one problem. They form a chain:

-   **Signal capture:** did the system observe the condition?
-   **Occurrence recording:** did it create a durable record for this
    particular episode?
-   **Operational response:** was someone explicitly responsible for
    mitigation?
-   **Recovery:** did the service/condition return to an acceptable
    state?
-   **Problem treatment:** was the underlying recurring condition
    understood and addressed?
-   **Assurance:** did the retrospective produce durable actions and
    controls, and were they verified?

A design that records only the alert rule or only the remediation task
loses the episode history. A design that records only the episode loses
the persistent condition and follow-up. A design that records only the
postmortem loses the operational command and timeline.

## 3. The proposed A/W/R model

### 3.1 A: one operational occurrence

An A-card represents one episode of an operational condition.

Properties:

-   It is created from a durable observation or alert transition.
-   It has a unique identity.
-   It is immutable as an occurrence record: it is never reopened.
-   Mitigation and recovery are evidenced by witnesses rather than
    inferred from the disappearance of an alert alone.
-   A later re-fire creates a new A-card and links it to the earlier
    episode and the persistent condition, where known.
-   It may be undeclared or declared. Not every alert episode must
    become a formally commanded incident.
-   It carries or references the command record, activity ledger,
    relevant signals, and bounded next action.

An A-card is not simply "the current state of an alert." It records an
occurrence in time. The same alert fingerprint may participate in
multiple episodes.

### 3.2 W: one persistent condition and its corrective obligation

A W umbrella represents a persistent condition, problem, or corrective
obligation that may have one or many A occurrences.

Properties:

-   It is not minted for every firing.
-   It groups related episodes under a durable condition identity.
-   It owns or organizes corrective action items as children.
-   It remains open until its actions are completed or it receives an
    explicit, evidenced disposition.
-   It may represent a known error, workaround, remediation plan,
    accepted residual risk, or a condition judged not to require further
    action.
-   A new A occurrence can recur against the same W condition.

The W should generally represent a condition, not an alert rule. One
rule may detect multiple distinct conditions, and multiple rules may
detect the same underlying condition. Rule identity and problem identity
are not interchangeable.

### 3.3 R: retrospective assurance

Nemik already has an R/retrospective vocabulary. Reuse it.

An R record should review an A occurrence, a W condition, or a related
group of occurrences and changes. Its findings should terminate in one
of:

-   a W action item;
-   a checkable change in a verdict, policy, or control;
-   an explicit, evidenced disposition that no further action is
    warranted.

The R is not merely a narrative postmortem. It is an assurance object
whose findings and handoffs are traceable into the graph.

The existing retrospective vocabulary includes `nemik:Retro`,
`RetroFinding`, `RetroHandoff`, and `RetroPass` / `RetroFixpoint`
concepts. The described `docs/retro-audit.md` gates include captured
precommit state, frozen timeline, computed delta, trigger/root
distinction, decorrelated review, blameless root analysis, sustainment,
findings terminating in actions or verdict changes, handoff/fixpoint,
and enforcement at an adequate layer for recurring failures.

There is an implementation/documentation discrepancy to resolve: the
survey found G4 represented in `shapes.ttl`, while `docs/retro-audit.md`
still described the corresponding shape as absent. More importantly,
actual retrospective ingestion was not yet present in the surveyed
adapter: shapes were exercised on fixtures, not actual `nemik:Retro`
records. Do not treat fixture validation as proof of end-to-end
retrospective ingestion.

### 3.4 The three records are related, not nested versions of one record

A useful conceptual picture is:

``` text
Alert rule(s)
    |
    v
Signal event(s) -----> A occurrence 1 ----+
                         |                 |
                         +-> R review     |
                                           +----> W condition / problem
Signal event(s) -----> A occurrence 2 ----+          |
                                                      +--> W action item
                                                      +--> W action item
                                                      +--> R assurance / fixpoint
```

This is illustrative, not a prescribed RDF serialization. The important
point is that the occurrence, condition, action, and retrospective have
separate identities and closure semantics.

## 4. Cross-reference with ITIL

ITIL provides a useful distinction between incident management and
problem management.

### 4.1 Incident management maps primarily to A

ITIL incident management is concerned with restoring normal service
operation and minimizing adverse impact. That maps to the operational
occurrence and response represented by A:

-   detect and record the incident;
-   assess impact and urgency;
-   assign responsibility;
-   coordinate response;
-   mitigate and restore service;
-   close the incident with an adequate record.

The A record should preserve the episode even after the service
recovers. Closing A means the operational episode has been demobilized
and its closure evidence recorded. It does not mean the underlying
problem has been solved.

### 4.2 Problem management maps primarily to W

ITIL problem management is concerned with identifying and managing the
causes of incidents, reducing the likelihood and impact of recurrence,
and managing workarounds or known errors.

That maps to the W umbrella:

-   correlate related A episodes;
-   investigate the persistent condition;
-   record known errors and workarounds where appropriate;
-   create and prioritize corrective action;
-   verify that the condition has been addressed or explicitly
    dispositioned.

The distinction matters because an incident can be mitigated without its
cause being known, and a problem can remain open after the incident is
closed.

### 4.3 ITIL is not a reason to make every alert an incident

An alert or event is not automatically an incident. The outline's
declaration policy is useful: undeclared episodes still receive durable
A records, while declaration determines whether the episode enters the
full command/incident-response path.

This is a valuable separation:

-   **Event/observation:** something was detected.
-   **A occurrence:** a durable episode record was minted.
-   **Declaration:** the episode was judged to require formal incident
    command.
-   **W problem:** a persistent condition was identified for corrective
    treatment.

Do not collapse these into a single boolean such as `incident=true`.

### 4.4 Where Nemik goes beyond the ITIL vocabulary

ITIL provides process concepts and record categories. Nemik can make the
relationship between them executable:

-   occurrence and problem identities are explicit graph nodes;
-   corrective actions are W nodes in the existing dependency graph;
-   evidence-backed witnesses control state transitions;
-   rank emerges from graph topology rather than manually assigned
    priority scores;
-   a rank-inversion check can detect when a driver outranks its own
    required follow-up.

ITIL does not, by itself, provide this specific graph-enforced
scheduling mechanism.

## 5. Cross-reference with Google IMAG and SRE incident practice

Here, **IMAG** refers to Google's Incident Management at Google
approach, which draws heavily on Incident Command System concepts.

### 5.1 IMAG maps to the declared-A response path

The strongest IMAG ideas for this design are:

-   explicitly declare an incident;
-   establish a clear incident commander;
-   make mitigation the immediate operational objective;
-   assign roles and responsibilities;
-   maintain a shared operational picture;
-   transfer command explicitly when responsibility changes;
-   demobilize deliberately rather than simply ceasing activity.

This maps naturally to a declared A occurrence.

A declaration should be an event or state transition with provenance,
not merely an editable boolean. It should record who or what declared
the incident, when, under which policy, and on what evidence.

### 5.2 Keep command separate from the session that happens to execute work

The outline maps the incident commander to the owning session, with the
host acting as commander when no owner exists. This is a practical
initial mapping, but it risks confusing:

-   **command authority:** who is accountable for the incident;
-   **execution ownership:** which session or agent performs a task;
-   **dispatch:** which component routes events and notifications;
-   **supervision:** who can intervene or approve exceptional decisions.

A session can hold multiple roles for a small incident, but the roles
should remain separately represented. This allows a later transfer or
split without changing the identity of the incident.

A command assignment should include at least:

-   incident/A identity;
-   commander identity;
-   accepted-at event;
-   current status;
-   scope of authority;
-   transfer history;
-   outgoing/incoming commander identities for a transfer;
-   explicit acceptance by the incoming commander.

A transfer is not complete merely because a new owner field was written.
It is complete when the receiving commander accepts responsibility and
the transfer record is durable.

### 5.3 IMAG and postmortems are related but not identical

IMAG is incident-response organization. Google's SRE postmortem practice
provides the follow-up discipline:

-   document impact and timeline;
-   distinguish trigger from root causes and contributing factors;
-   identify what went well and what did not;
-   create action items with owners and tracking;
-   follow action items through completion;
-   focus on learning and system improvement rather than blame.

The R model should provide this assurance path. Do not treat "postmortem
written" as equivalent to "postmortem actions completed."

### 5.4 Mitigation first does not mean corrective work must wait

During an active incident, restoring service is the immediate
operational priority. But that does not imply that all corrective W work
must wait until A closes. Some safe, bounded corrective work can proceed
in parallel, provided it does not interfere with mitigation or create
conflicting command.

The graph should express the actual dependency. Avoid a blanket rule
that every W child is blocked by the entire A lifecycle.

## 6. Cross-reference with the Incident Command System (ICS)

ICS provides the strongest operational structure for command, transfer,
coordination, planning, logging, and demobilization.

### 6.1 Single command and unified command

A single incident should have one clearly accountable incident command
function.

When multiple organizations or owners share authority, **Unified
Command** is not merely several independent commanders attached to the
same card. It is a joint command function with shared objectives and
coordinated decisions.

For Nemik:

-   a single-owner incident can have one commander;
-   a cross-owner incident can have a Unified Command record;
-   contributing owners can retain responsibility for their own work
    without becoming independent incident commanders;
-   command membership and authority must be explicit and auditable.

The graph should distinguish command membership from task ownership.

### 6.2 Transfer of command

ICS emphasizes an orderly transfer with briefing and acceptance. A Nemik
transfer should preserve:

-   current situation and impact;
-   objectives and priorities;
-   current actions and assignments;
-   known hazards and constraints;
-   unresolved questions and evidence;
-   incoming and outgoing command identities;
-   transfer time/event;
-   explicit acceptance.

This is a durable state transition, not a mutable owner label.

### 6.3 Incident Action Plan versus `next_bounded_step`

The outline proposes `next_bounded_step` as the A-card's incident action
plan. This is a useful compact operational field, but it is not
equivalent to a full ICS Incident Action Plan.

An IAP can include:

-   incident objectives;
-   operational-period strategy;
-   assignments and resources;
-   organization and communications;
-   safety considerations;
-   relevant maps, forms, and supporting information.

For an automated fleet incident, `next_bounded_step` can be the
immediate executable action while the A record references a richer
action-plan object or a set of typed fields. Do not imply that one
string field captures the full IAP semantics.

### 6.4 Activity log and ICS-214

The A ledger is analogous to an ICS-214 activity log. It should be a
durable, append-oriented record of operationally relevant events:

-   alert/signal transitions;
-   declaration;
-   command assignment and transfer;
-   decisions;
-   actions and outcomes;
-   mitigation and recovery evidence;
-   demobilization;
-   material changes in understanding.

The current outline says the activity log is scattered. This is a
concrete gap. The A record should provide one canonical event stream or
a canonical ordered projection over source events. Do not copy
unverified summaries into it and call them the source of truth.

### 6.5 Demobilization is not the same as recovery

Recovery means the service or operational condition has returned to an
acceptable state. Demobilization means the incident organization has
stood down and resources/roles have been released or reassigned.

These can happen at different times. A system can be technically
recovered while the incident command function is still coordinating
verification, handoff, or safe shutdown. Conversely, an incident can be
demobilized while longer-term W remediation remains open.

### 6.6 Span of control

ICS uses span-of-control guidance, often taught with a preferred range
around three to seven reporting elements and a target of five. Do not
turn that into an unconditional hard-coded law for agent sessions.

For Nemik, begin with a conservative cap that prevents one commander
from silently accumulating too many open A incidents. Then measure
actual load:

-   number of open incidents;
-   number of active assignments;
-   event rate;
-   decision/coordination load;
-   cross-owner complexity;
-   age and severity of unresolved work.

A learned or adaptive limit is plausible later, but a system should not
learn its way into unsafe overload. Keep a hard safety bound while
calibrating the operational target from evidence.

## 7. Cross-reference with Prometheus and Alertmanager

The Prometheus alerting model supplies an important identity
distinction:

-   **Alert rule:** the definition of a condition to evaluate.
-   **Alert instance:** a particular label set/fingerprint produced by
    evaluating that rule.
-   **Episode:** a bounded occurrence over time.
-   **Problem/condition:** the persistent underlying issue that may
    produce multiple episodes.

A fingerprint is not an episode ID. The same fingerprint can fire,
resolve, and fire again. If the A identity is only the fingerprint,
separate episodes collapse into one record and the history becomes
ambiguous.

### 7.1 Recommended identity chain

Represent, at least conceptually:

1.  rule identity;
2.  alert instance identity/fingerprint;
3.  signal transition/event identity;
4.  A episode identity;
5.  W condition identity.

An episode can be derived from a durable firing transition or
generation, but it must be stable under duplicate delivery and distinct
across genuine re-fires.

### 7.2 Delivery semantics

Alert delivery is not guaranteed to be exactly once. The architecture
should tolerate:

-   duplicate notifications;
-   out-of-order transitions;
-   process restart between receipt and persistence;
-   lost notifications;
-   stale/replayed events;
-   alert recovery arriving before a delayed firing event;
-   multiple producers reporting related observations.

The durable event/occurrence record must be idempotent. Notification
should follow durable persistence, not precede it. A reconciler should
be able to reconstruct missing A records from the authoritative signal
history where possible.

### 7.3 Rule identity is not problem identity

One alert rule may match many distinct resources or conditions. Several
rules may expose different symptoms of one underlying condition.
Therefore:

-   do not automatically create one W per alert rule;
-   do not assume one alert fingerprint equals one W;
-   allow an A to exist before its W condition is known;
-   allow multiple A occurrences to be correlated to one W later;
-   preserve uncertainty in the correlation.

### 7.4 Learned baselines are not declaration policy

The outline proposes declaration as a stated rule over alert labels and
duration, using learned baselines rather than hand-typed thresholds.

Separate two concerns:

-   **Baseline model:** what is normal for this signal or system, with
    uncertainty and data quality.
-   **Declaration policy:** under what conditions an episode warrants
    formal command.

A learned baseline should specify or expose:

-   training population and scope;
-   observation window;
-   minimum sample count;
-   confidence/uncertainty;
-   missing-data behavior;
-   stale-data behavior;
-   drift detection;
-   hysteresis or stability requirements;
-   model/version provenance.

A learned baseline must not silently convert missing or unobservable
telemetry into "normal." The policy should explicitly handle unknown,
stale, and failed producers.

## 8. Cross-reference with Nemik as currently understood

This section distinguishes the existing Nemik architecture described in
the prior survey from the proposed extensions. The surveyed public
`main` snapshot was at W2164 (`e496230171b7`, 2026-11-13 12:25:48 UTC).
The outline refers to W2166, so W2166 behavior was not present in that
inspected snapshot and should be treated as proposed or in flight unless
separately verified.

### 8.1 Existing weather cards are dependency/weather records, not incident records

The existing weather model has these properties:

-   weather is represented as W cards;
-   the blocked repository owns the weather card;
-   the card is tied to a Rego witness;
-   a normalized witness query hash is used to group equivalent weather;
-   the witness closes the card when the condition holds;
-   the card is monotone and is not reopened;
-   a new outage produces a new W card.

This is useful for representing a work item waiting on an external
condition. It is not a canonical incident-management record.

The distinction is important:

-   a weather card says, in effect, "this work is blocked until this
    external condition is satisfied";
-   an A card says "this operational episode occurred, and here is its
    durable history and command/mitigation lifecycle."

The two may be related, but they should not be the same resource.

### 8.2 A should be a distinct resource type, not W with a prefix

Adding an `A` namespace is not sufficient if the implementation still
treats A as an ordinary W in every behavioral path.

A must have distinct:

-   identity allocation;
-   schema and validation;
-   lifecycle;
-   command semantics;
-   closure witnesses;
-   read-model presentation;
-   scheduling/ranking treatment;
-   dependency interpretation;
-   tests.

A should not automatically enter the ready-work queue or be treated as
ordinary work to be scheduled. Its operational response path is distinct
from corrective W work.

### 8.3 Reuse Nemik's graph and umbrella machinery

Do not create a parallel parent/child model for incidents and
postmortems. Reuse the existing graph machinery where its semantics fit:

-   W umbrellas and child action items;
-   dependency closure;
-   `blocked_on` / `enables`;
-   blocker resolution;
-   rank calculation;
-   witness evaluation;
-   graph projections and operator views.

Extend the resolver and projections to understand A references where
appropriate. Do not force every A relationship into W's existing
`blocked_on` semantics.

The graph should distinguish at least:

-   operational dependency: a task cannot safely proceed while an
    incident state is active;
-   corrective dependency: a driver/change is held until required
    follow-up is complete;
-   causal attribution: a change may have caused or contributed to an
    incident;
-   historical association: an occurrence concerns a persistent
    condition;
-   retrospective relation: an R reviews an occurrence/condition and
    emits findings.

These are different relations and should not be overloaded into one
generic edge.

### 8.4 Reuse the R model, but close the ingestion gap

The existing R vocabulary is the natural home for post-incident review.
However, the surveyed state showed that actual retrospective ingestion
was missing from the adapter. A shape tested only against fixtures is
not an operationally integrated record.

Before relying on R to close umbrellas, ensure:

-   actual R records can be ingested;
-   required evidence is available from real source records;
-   SHACL validation applies to those records;
-   findings link to real W actions or checkable verdict changes;
-   closure/fixpoint is computed from those real records;
-   tests cover the complete ingestion-to-projection path.

Also reconcile the G4 documentation/shape discrepancy.

### 8.5 Keep the mtools writer / Nemik reader boundary

The existing architecture places queue mutation in mtools and graph
interpretation in Nemik. Preserve that separation.

-   mtools owns the writer and namespace allocation mechanism;
-   luthen-observability detects signals and invokes the appropriate
    mtools writer;
-   Nemik reads the resulting ledger, resolves graph relationships,
    evaluates witnesses, computes rank, and exposes the operator view.

Do not have luthen-observability write queue files directly if the
established writer boundary says it should call mtools. Do not make
Nemik reach outward and become the producer of the incident record.

This preserves the principle that the agent invokes Nemik; Nemik does
not dispatch or author work by itself.

### 8.6 Keep telemetry as the operational evidence source

The design should preserve the stated observability principle: telemetry
is the primary source of truth for operational signals. The incident
ledger is the durable record of episode identity, command, decisions,
and references to evidence; it should not invent telemetry values or
become a competing measurement system.

For every signal, distinguish:

-   observed true;
-   observed false;
-   unknown;
-   stale;
-   producer failed;
-   unobservable due to permissions or collection coverage.

The k3s/drum example's root `/proc` visibility gap is important: a
producer that cannot see root-owned tasks must not report "zero held
execs." It must report that the measurement is incomplete or
unavailable. The held-execs count must come from a producer with
sufficient privilege and coverage.

### 8.7 Event-driven wake-up should not become a third oversight loop

The outline's desired flow is sound:

-   luthen's alert monitor observes alert transitions;
-   a durable A record is minted through mtools;
-   the relevant owning session is notified or its in-session monitor
    fires;
-   Nemik evaluates the graph and witnesses;
-   watchdogs reconcile as a backstop.

This is not a new independent oversight loop. It is an event-driven path
through existing producers, ledger writer, graph reader, and session
monitors.

`nemik-wake`, as surveyed, is a liveness/dependency wake roster
(`asleep` / `idle` / `awake` / `unknown`), not an event dispatcher. Hook
event capture in `~/.local/state/nemik/events.jsonl` records local
session timing/context without prompt text or network, but it is not a
durable alert-transition or incident activity ledger. Do not conflate
these systems.

### 8.8 Preserve Nemik's topology-derived ranking

The ranking principle is that priority emerges from graph topology, not
manual weights. The proposed rule that cleanup and follow-up outrank new
debt should be enforced structurally.

However, do not assume the outline's W2166 behavior was already present
in the surveyed W2164 snapshot. Treat it as a target until verified.

A rank-inversion check should detect a driver ranked above the follow-up
that is supposed to gate it. But the test must also prove:

-   the graph remains acyclic where required;
-   unrelated work is not accidentally blocked;
-   the follow-up is actually reachable and rankable;
-   the driver is blocked for the correct reason;
-   completing the follow-up unblocks the intended driver;
-   no unrelated work is given an unintended priority boost.

## 9. Refine the identity and relationship model

The outline's four main identities---A episode, W umbrella, action-item
W, and driver---need a little more precision.

### 9.1 Separate the change roles

"Driver" is currently defined as the card whose change caused, or keeps
causing, the weather. That can conflate several roles:

-   **triggering change:** the change/deployment that immediately
    preceded or triggered the episode;
-   **causal change:** a change established by evidence to have caused
    the condition;
-   **contributing change:** a change that increased likelihood, impact,
    or duration;
-   **affected change:** a change whose execution or outcome was
    affected by the incident;
-   **remediation change:** the change intended to correct the
    condition;
-   **follow-up obligation:** the W action item that must be completed
    before a particular driver can be considered finished.

These should not all be called "driver." The k3s example's W2564 re-land
needs an explicit classification before the graph can safely use it as
the causal or gating object.

### 9.2 Preserve unknown attribution

When the cause is unknown, there should be no causal edge. That is
correct. But absence of a causal edge must not be interpreted as absence
of impact or absence of an operational dependency.

Use explicit attribution states, such as:

-   unknown;
-   suspected;
-   confirmed;
-   rejected.

The state should have evidence and provenance. A suspected cause should
not silently become a confirmed cause because it is convenient for
ranking.

### 9.3 Keep causality separate from dependency

A causal relation says something about why an incident occurred. A
dependency relation says what must happen before work can proceed. These
are not equivalent.

The outline suggests that the driver is blocked on both A and the W
umbrella. This may be correct for a change that is still in flight or
for a change that must not be considered complete until follow-up is
done. It is not automatically correct for a historical deployment that
has already landed and cannot meaningfully be "un-landed" or held.

Use separate predicates/edge types for:

-   `causedBy` / `contributedTo` (attribution);
-   `concernsCondition` / `hasOccurrence` (association);
-   `blockedOn` / `enables` (work dependency);
-   `reviews` / `hasFinding` (retrospective);
-   `recursAfter` (episode history);
-   `mitigatedBy` / `recoveredBy` (evidence or action relation).

Predicate names are illustrative. Choose names consistent with the
existing ontology and PROV semantics.

In particular, do not casually use `prov:wasInformedBy` to mean "caused
by." PROV has defined activity/entity semantics; use it only when the
subject/object types and meaning match. A local causal predicate may be
clearer.

### 9.4 Avoid cycles introduced by follow-up edges

If the driver blocks on the umbrella and the umbrella's action items
depend on the driver, the graph may form a cycle. The W2595 gate
deadlock in the worked example makes this a concrete acceptance test,
not a theoretical concern.

Before adding a gating edge, prove that:

-   the edge has the intended direction;
-   it does not create a cycle;
-   the umbrella can make progress independently of the blocked driver
    where appropriate;
-   action items can be completed without requiring the blocked driver
    to complete first;
-   the graph's closure/rank algorithms handle the new relation
    correctly.

## 10. Separate lifecycles

The outline currently gives a single lifecycle:

`Fire → mint A → (declare?) → command assigned → mitigate (witness) → A closes (demobilize) → postmortem → action items → umbrella closes → driver unblocked`

This is too linear. A, W, and R have related but independent lifecycles.

### 10.1 A occurrence lifecycle

A practical state model is:

``` text
Observed
   |
   v
Recorded
   |
   +----> Undeclared ----> Mitigated/Recovered ----> Closed
   |
   +----> Declared
             |
             v
       Command accepted
             |
             v
         Responding
             |
             v
       Mitigation witnessed
             |
             v
       Recovery witnessed
             |
             v
         Demobilizing
             |
             v
           Closed
```

The exact state names can change, but the transitions must be explicit
and evidence-backed.

Important points:

-   `Recorded` means the occurrence has a durable identity.
-   `Declared` means it has entered the formal command path.
-   `Command accepted` means an accountable commander has accepted
    responsibility.
-   `Mitigated` means an immediate intervention reduced the operational
    impact or stabilized the situation.
-   `Recovered` means the relevant service/condition has returned to an
    explicitly defined acceptable state.
-   `Demobilizing` means command and resources are being stood down.
-   `Closed` means the occurrence record is complete enough to close,
    not that the underlying problem is solved.

Undeclared episodes can take a simpler path, but they should still
retain occurrence history and appropriate closure evidence.

### 10.2 W condition lifecycle

A W umbrella can follow a separate path:

``` text
Identified
   |
   v
Investigating
   |
   +----> Cause unknown / investigation continues
   |
   v
Known condition / workaround recorded
   |
   v
Corrective actions created
   |
   v
Actions completed
   |
   v
Outcomes verified
   |
   v
Closed or explicitly dispositioned
```

The W can remain open while all associated A occurrences are closed. A
later A can recur against the same W condition. The W can also be
investigated and remediated while an A is still active, if doing so is
safe and useful.

### 10.3 R retrospective lifecycle

R can begin before A closes, but the final retrospective should have
access to a sufficiently frozen timeline and evidence set.

``` text
Triggered
   |
   v
Evidence/timeline assembled
   |
   v
Review performed
   |
   v
Findings recorded
   |
   +----> W action items
   |
   +----> Checkable control/verdict changes
   |
   v
Handoff and sustainment
   |
   v
Fixpoint/assurance decision
```

A retrospective fixpoint means the review process has no further
findings under its declared scope. It does not prove that the system is
correct or that recurrence is impossible. Outcome verification is a
separate requirement.

## 11. Declaration and promotion

The outline's declaration rule is a useful direction:

-   declaration is a stated rule over alert labels and duration;
-   learned baselines replace hand-typed thresholds;
-   undeclared episodes still receive A records;
-   recurrence can promote a condition to declared.

Refinements:

1.  Declaration should be a recorded transition with policy/version and
    evidence.
2.  The baseline model and declaration policy should be independently
    versioned.
3.  Promotion should attach prior related A occurrences to the newly
    identified W condition.
4.  Promotion should not rewrite historical occurrence facts. It adds a
    relationship or classification with provenance.
5.  A condition can be declared based on impact or risk even without
    recurrence; recurrence should be one possible promotion signal, not
    necessarily the only one.
6.  An episode can be declared even when the root cause is unknown.
7.  A re-fire after recovery is a new A occurrence, not a reopening of
    the previous A.

## 12. Command, ownership, and routing

The outline's role mapping is a useful starting point:

-   incident commander: owning session, with host as initial commander
    when no owner exists;
-   unified command: incident spans owners;
-   dispatcher: luthen alert monitor;
-   operator: supervisor, not routine on-call;
-   span of control: bounded number of open A cards per commander;
-   IAP: A's next bounded step;
-   activity log: A ledger.

Tighten it as follows:

-   **Dispatcher is not commander.** The alert monitor detects and
    routes; it does not automatically own command.
-   **Operator is not incident commander by default.** The operator
    supervises policy, exceptional decisions, and escalation.
-   **Owning session is not automatically commander.** It becomes
    commander when assigned and accepted.
-   **Host as fallback commander requires an explicit
    assignment/acceptance record.** "No owner" must not silently mean
    "the host owns it."
-   **Unified Command is a joint command record.** It is not a list of
    owners who happen to be involved.
-   **Task ownership is independent of command membership.** An owner
    can execute an assigned action without becoming incident commander.

For a small incident, one session may perform several roles. The
representation should still preserve the role distinctions so the system
can later split them.

## 13. Event-driven waiting and reconciliation

The desired event-driven architecture is:

``` text
Signal producer / Alertmanager
          |
          v
Durable transition event
          |
          v
mtools writer allocates A identity and persists occurrence
          |
          +------> notification / owning-session monitor
          |
          v
Nemik reads ledger and evaluates graph/witnesses
          |
          v
Operator view / rank / dependency updates

Watchdog: reconciliation and recovery backstop only
```

Key invariants:

1.  Persist the event/occurrence before notifying a session.
2.  A duplicate event must not mint a duplicate A.
3.  A genuine re-fire must mint a new A.
4.  A missed notification must be recoverable from the durable
    ledger/event stream.
5.  A process restart must not lose the transition between receipt and
    persistence.
6.  Out-of-order transitions must be reconciled deterministically.
7.  Watchdogs are a backstop, not the primary mechanism for noticing
    incidents.
8.  In-session monitors can wait on live conditions, but cross-session
    state must be durable and replayable.

The proposed in-session Monitor loop is consistent with the goal of
event-driven work. The watchdog interval (45 minutes in the outline)
should not become the semantic definition of an incident or a
correctness timeout. The user's broader operator stance is that
wall-clock contention should not be treated as a correctness failure;
use event/evidence state and measured resource/CPU behavior where
appropriate.

## 14. Producers, telemetry, and truthfulness

The outline correctly calls out truthful signals and root-level producer
visibility.

A signal should carry enough metadata to establish:

-   producer identity and version;
-   observation time and ingestion time;
-   scope/resource identity;
-   privilege/visibility scope;
-   freshness;
-   sampling or aggregation method;
-   units and interpretation;
-   confidence or quality state;
-   whether the producer was healthy and capable of observing the
    relevant population.

A missing observation is not zero. A process scan that cannot see root
tasks must produce an unknown/incomplete measurement, not a zero count.
This should be a tested contract.

The telemetry system remains the primary source for operational
measurements. The A ledger should preserve durable event history,
decisions, command transitions, and evidence references. The W/R graph
should reason over those records without fabricating measurement facts.

The btrfs, btrbk, bees, and other panels/forecasts mentioned in the
outline should be treated as signal producers or evidence sources with
explicit coverage and freshness, not merely as dashboard decorations.

## 15. Namespace and identifier design

The outline proposes a declared namespace table, with W, R, and A each
having a monotone counter and never-reused symbols.

This is sound in principle, but the ownership and scope must be
explicit.

Questions to resolve:

-   Is the namespace table global to the fleet or scoped to a
    repository?
-   Is the canonical identity `<repo>:A<n>` or a fleet-global A
    identity?
-   Which repository owns an incident spanning several repositories?
-   Can a single A reference evidence and W records in multiple
    repositories?
-   How are identities allocated atomically under concurrent writers?
-   What happens when a writer retries after a partial failure?

A practical default is repository-scoped identity with an explicit
canonical owning repository, unless fleet-wide uniqueness is a hard
requirement. Cross-repository relationships should reference the
canonical identifier rather than mint aliases. The namespace allocator
and writer should be owned by mtools, with monotonicity and non-reuse
tested under concurrency and retry.

The migration rule is good:

-   existing weather W symbols retain their identity;
-   do not create aliases that pretend old W weather records were A
    records;
-   new operational occurrences use A;
-   retro-fit the k3s outage as the first worked example without
    rewriting history.

## 16. Ranking and corrective-work priority

The goal "cleanup and follow-up outrank new debt by construction" is
important. It should be achieved through graph structure rather than
hand-authored numeric weights.

The outline says the driver is blocked on both A and the W umbrella.
This needs two distinct gating decisions:

-   **Operational gate:** a change/task cannot safely proceed while the
    relevant incident is active.
-   **Corrective gate:** a change cannot be considered complete or fully
    released from follow-up until required corrective work is complete
    or dispositioned.

Do not apply either gate indiscriminately. A historical deployment may
already be landed; it cannot necessarily be blocked in a useful sense. A
remediation action may need to proceed during the incident. The graph
must represent the actual work semantics.

Tests should prove:

-   required follow-up outranks unrelated new debt under the intended
    conditions;
-   the driver cannot be declared complete while mandatory follow-up is
    outstanding;
-   unrelated work is not accidentally blocked;
-   a remediation action can proceed when it is supposed to;
-   completing or dispositioning the follow-up unblocks the intended
    node;
-   no cycle is introduced;
-   rank remains deterministic;
-   no manual priority weight is needed to obtain the result.

A rank-inversion check should be a hard invariant only where the graph
semantics establish that the follow-up is mandatory and the driver is
legitimately gated by it.

## 17. Empty umbrellas and explicit disposition

An umbrella with no action items must not close merely because it is
empty. It needs an explicit disposition and evidence.

Possible dispositions include:

-   cause disproven;
-   no corrective action justified;
-   existing control demonstrated sufficient;
-   accepted residual risk;
-   superseded by another condition/problem;
-   duplicate of another W condition.

The R record should justify the disposition. This prevents "no children"
from becoming an accidental proof of "nothing to do."

## 18. The k3s/drum outage as the acceptance case

The 2026-11-13 k3s/drum outage should be the first end-to-end example
and acceptance suite.

The outline records:

-   A occurrence: outage, mitigated at approximately 11:56Z;
-   W umbrella: postmortem, with W2593--W2601 as action items;
-   driver: W2564 re-land, blocked on both A and W umbrella;
-   exposed gaps:
    -   activity log scattered;
    -   command implicit;
    -   gate deadlocked (W2595);
    -   session `/proc` scan blind to root tasks.

Turn each gap into a concrete test or control:

1.  **Scattered activity log:** all operationally relevant events are
    queryable from the A activity ledger or canonical projection.
2.  **Implicit command:** no declared A can enter the response state
    without an accepted command assignment or explicit documented
    exception.
3.  **Gate deadlock:** graph construction rejects or detects the W2595
    cycle; a valid remediation path remains reachable.
4.  **Blind `/proc` scan:** producer coverage/privilege is represented;
    incomplete visibility cannot be reported as zero.
5.  **Driver attribution:** W2564 is classified as triggering, causal,
    contributing, affected, or remediation-related with evidence.
6.  **Follow-up priority:** W2593--W2601 receive the intended rank and
    gating behavior without blocking unrelated work.
7.  **Retrospective ingestion:** the actual R record is ingested,
    validated, projected, and linked to its findings.
8.  **Re-fire:** a later episode creates a new A linked to the same W
    condition where appropriate.

The worked example should be executable as a fixture or integration
scenario, not merely a prose narrative.

## 19. Open questions and recommended decisions

  -----------------------------------------------------------------------
  Question in outline                 Recommendation
  ----------------------------------- -----------------------------------
  Where does the namespace table live mtools owns the authoritative
  and what format?                    allocator/table; choose
                                      repository-scoped or fleet-global
                                      identity explicitly and test
                                      concurrency/retry.

  Is span-of-control fixed or         Start with a conservative hard
  learned?                            safety cap; measure load and
                                      calibrate the operating target.

  What closes an umbrella with no     An explicit R-backed disposition,
  action items?                       never emptiness alone.

  How does owner routing interact     Route tasks to owners; represent
  with Unified Command?               Unified Command separately as joint
                                      command authority.

  Does the loop prompt change?        Not yet. Validate the mechanics and
                                      acceptance tests before changing
                                      the prompt.

  What is the driver?                 Split trigger, cause, contributor,
                                      affected change, remediation
                                      change, and gating obligation.

  What is an episode ID?              A durable
                                      firing-generation/transition
                                      identity, not an alert fingerprint
                                      alone.

  What does A closure mean?           Operational episode demobilized and
                                      evidence complete; it does not
                                      close W.

  What does R fixpoint mean?          No further findings under the
                                      declared review scope; not proof of
                                      system correctness.
  -----------------------------------------------------------------------

## 20. Measures and witnesses

The outline's proposed measures are useful:

-   time from fire to A-card;
-   time from mitigation to umbrella close;
-   open action items by age;
-   rank-inversion check.

Expand them to cover the full lifecycle:

-   signal transition to durable A persistence;
-   persistence to declaration;
-   declaration to command acceptance;
-   command acceptance to first mitigation action;
-   mitigation action to mitigation witness;
-   mitigation to stable recovery;
-   recovery to demobilization;
-   command transfer count and transfer-acceptance latency;
-   unacknowledged command assignments;
-   recurrence count per W condition;
-   age and completion rate of W action items;
-   time from A closure to R completion;
-   time from R finding to action creation;
-   percentage of findings linked to an action or checkable verdict
    change;
-   outcome-verification success/failure;
-   unknown/suspected/confirmed causal attribution distribution;
-   stale, failed, or unobservable producer rates;
-   rank inversions and graph-cycle detections;
-   duplicate and out-of-order event handling;
-   missed-notification recovery through reconciliation.

Avoid treating elapsed wall time as the only measure of correctness.
Time-based service objectives may still be operationally useful, but
distinguish service-level performance from semantic state validity and
resource contention.

Every measure should have a defined producer, unit, scope, freshness
contract, and failure behavior.

## 21. Implementation sequence

A staged implementation reduces the chance of building a parallel
incident subsystem that later has to be reconciled with Nemik.

### Stage 1 --- vocabulary and identity

1.  Define A, W-condition, W-action, and R identities and their
    relationships.
2.  Decide namespace scope and canonical ownership.
3.  Define alert rule, alert instance, signal event, and episode
    identity separately.
4.  Define attribution roles and uncertainty states.
5.  Document lifecycle and closure semantics.

### Stage 2 --- writer and schema

6.  Add the A namespace and monotone allocator in mtools.
7.  Add A record writer operations through the established mtools
    boundary.
8.  Define A schema/SHACL shapes and transition invariants.
9.  Test concurrency, retries, duplicate writes, and symbol non-reuse.

### Stage 3 --- Nemik read and graph integration

10. Ingest A records into Nemik's model.
11. Extend reference validation, blocker resolution, graph projections,
    and operator views.
12. Add explicit relationship types for occurrence, condition,
    causality, operational dependency, corrective dependency, and
    retrospective review.
13. Keep A out of ordinary ready-work scheduling unless a specific
    operational command/assignment projection requires it.
14. Add graph-cycle and rank-inversion checks.

### Stage 4 --- signals and event path

15. Integrate vmalert/Alertmanager transitions through a durable event
    path.
16. Make A minting idempotent and episode-aware.
17. Persist before notifying sessions.
18. Add event replay/reconciliation for restart, loss, duplicates, and
    out-of-order delivery.
19. Add declaration policy and learned-baseline provenance.
20. Add owner routing and session monitors after durable event semantics
    work.

### Stage 5 --- command and evidence

21. Add command assignment and acceptance.
22. Add transfer-of-command records and explicit acceptance.
23. Add Unified Command representation for cross-owner incidents.
24. Add append-oriented activity ledger/projection.
25. Define mitigation, recovery, and demobilization witnesses
    independently.

### Stage 6 --- W/R integration and ranking

26. Create W umbrellas for persistent conditions, not merely alert
    rules.
27. Attach related historical and future A occurrences.
28. Ingest actual R records, not only fixtures.
29. Link R findings to W actions or checkable verdict changes.
30. Define explicit empty-umbrella dispositions.
31. Prove topology-derived follow-up priority and absence of deadlocks.

### Stage 7 --- operational acceptance

32. Implement the k3s/drum outage as the first complete worked example.
33. Run the identity, lifecycle, event-delivery, command,
    producer-coverage, graph, rank, and retrospective tests.
34. Add measures and witnesses.
35. Only then reconsider the loop prompt or broader fleet rollout.

## 22. Acceptance-test matrix

  --------------------------------------------------------------------------------------
  Area                    Required behavior                      Failure that the test
                                                                 must catch
  ----------------------- -------------------------------------- -----------------------
  Identity                Duplicate delivery maps to the same A; Duplicate A or
                          genuine re-fire maps to a new A        collapsed episodes

  Namespace               Counters are monotone and symbols are  Collision or reuse
                          never reused                           after retry/restart

  Declaration             Undeclared A remains durable;          Alert silently
                          declaration is recorded with           disappears or boolean
                          provenance                             flips without evidence

  Command                 Declared incident has an accepted      Implicit ownership
                          commander                              

  Transfer                Incoming commander explicitly accepts  Owner field changes
                          a durable transfer                     without handoff

  Unified Command         Shared authority is represented as one Several uncoordinated
                          joint command function                 commanders

  Activity log            Relevant events are queryable in order Scattered or missing
                                                                 timeline

  Mitigation              Mitigation witness proves the defined  Alert disappearance
                          mitigation condition                   treated as mitigation

  Recovery                Recovery witness is distinct from      Temporary stabilization
                          mitigation                             treated as full
                                                                 recovery

  Demobilization          Command/resources stand down           A closes while command
                          explicitly                             remains ambiguous

  Telemetry               Missing/stale/unobservable data        Missing producer data
                          remains unknown                        becomes zero/healthy

  Event delivery          Replay/reconciliation repairs missed   Cron tick is the only
                          notifications                          discovery mechanism

  Causality               Unknown/suspected/confirmed/rejected   Guess becomes causal
                          are distinct                           fact

  Graph                   Edges have typed semantics and no      W2595-style deadlock
                          unintended cycle                       

  Ranking                 Required follow-up outranks relevant   Driver outranks
                          new debt                               mandatory follow-up

  Isolation               Unrelated work is not blocked          Broad accidental
                                                                 dependency

  R ingestion             Real retrospective records validate    Fixtures pass while
                          and project                            production ingestion is
                                                                 absent

  R findings              Findings terminate in actions or       Narrative-only
                          checkable verdict changes              postmortem

  Umbrella closure        Empty umbrella requires explicit       Empty means done
                          disposition                            

  Recurrence              New A attaches to existing W when      Reopened A or
                          correlation is established             fragmented problem
                                                                 history
  --------------------------------------------------------------------------------------

## 23. What is established, what is proposed, and what remains to verify

To keep implementation agents from treating design intent as existing
behavior, preserve these evidence boundaries.

### Established in the surveyed Nemik snapshot

-   Nemik is the ledger/graph reader and evaluator; mtools owns queue
    writing.
-   Existing W weather cards represent witness-backed external blocking
    conditions.
-   Existing weather cards are monotone and do not reopen.
-   Nemik has dependency, blocker, ranking, umbrella, and witness
    machinery.
-   `nemik-wake` is a liveness/dependency wake roster, not an event
    dispatcher.
-   Local hook event capture is not a durable incident activity ledger.
-   Retrospective vocabulary and shapes exist.
-   The surveyed adapter lacked actual retrospective ingestion.
-   W2163 addressed a publication race in `serve.Model.refresh()`.
-   W2164 reduced Codon wall incidence and replaced `shutil.copy2` with
    atomic copy.

### Proposed by the outline or this review

-   A as a distinct occurrence resource and namespace.
-   W umbrella per persistent condition.
-   A command/transfer/Unified Command records.
-   Durable event-driven A minting.
-   Alert fingerprint versus episode identity.
-   New typed relationships for occurrence, causality, and incident
    dependencies.
-   Follow-up ranking guarantee referenced as W2166.
-   The k3s/drum outage as the first end-to-end acceptance example.

### Not independently verified in the survey

-   The referenced mtools W2409/W2410 implementation details.
-   The referenced luthen-observability W2600--W2609 implementation
    details.
-   The current implementation state of nemik W2166.
-   Whether the other repositories already provide all required durable
    event, command, and producer-coverage mechanisms.

Treat those as claims to verify against the relevant repository
revisions before implementation.

## 24. Novelty and prior-art assessment

The proposal does not invent:

-   incident versus problem records;
-   incident declaration and command;
-   transfer of command;
-   unified command;
-   incident action planning;
-   activity logs;
-   demobilization;
-   post-incident reviews and tracked action items;
-   alert rule versus alert instance identity.

These are established in ITIL, Google SRE/IMAG, ICS, and
Prometheus/Alertmanager practice.

The more distinctive contribution is the integration:

1.  Every operational episode receives a durable, immutable identity.
2.  Persistent conditions have identities separate from individual
    episodes.
3.  Corrective obligations are represented in the same dependency graph
    as engineering work.
4.  Operational command and causal attribution are represented
    explicitly rather than inferred from session ownership or card
    proximity.
5.  Evidence-backed witnesses govern mitigation, recovery, and closure.
6.  Corrective follow-up is made structurally visible and rankable,
    rather than left as prose in a postmortem.
7.  Retrospective findings feed back into W actions or checkable control
    changes.
8.  Event-driven notification is layered over durable ledger state, with
    reconciliation as a backstop.

That combination is a meaningful architecture-level synthesis. Its value
depends on whether the distinctions are genuinely implemented and
tested, not on the names A/W/R.

## 25. Final design rules

The following rules are suitable as direct design constraints for
implementation agents:

1.  **A is an occurrence, not a condition.** Never reopen an A. A
    re-fire creates a new A.
2.  **W is a persistent condition or corrective obligation, not an alert
    rule.** One W can have many A occurrences.
3.  **R is assurance, not merely narrative.** Findings must produce
    actions, checkable verdict changes, or evidenced dispositions.
4.  **Detection is not declaration.** Undeclared episodes still receive
    durable A records.
5.  **Mitigation is not recovery.** Use distinct evidence and
    transitions.
6.  **Recovery is not demobilization.** Operational restoration and
    command stand-down are separate.
7.  **Incident closure is not problem closure.** A can close while W
    remains open.
8.  **A fingerprint is not an episode ID.** Handle repeated firings
    explicitly.
9.  **Causality is not dependency.** Use typed relationships and
    preserve attribution uncertainty.
10. **Command is not session ownership.** Assignment and acceptance must
    be recorded.
11. **Unified Command is joint authority, not multiple unrelated
    commanders.**
12. **An activity log is durable evidence.** Do not rely on scattered
    session output.
13. **Unknown telemetry is not zero.** Producer coverage and freshness
    are part of the measurement.
14. **Persist before notifying.** Event delivery must be idempotent and
    replayable.
15. **Watchdogs reconcile; they do not define the primary event path.**
16. **Reuse Nemik's W graph and R model.** Do not build parallel
    umbrella or postmortem systems.
17. **Preserve the mtools-writer/Nemik-reader boundary.**
18. **Do not turn A into ordinary ready work.** Model its
    command/response path separately.
19. **Do not close an empty umbrella by default.** Require an explicit,
    evidenced disposition.
20. **Prove rank behavior structurally.** Test both intended priority
    and absence of accidental blocking.
21. **Do not change the loop prompt before the mechanics are
    validated.**
22. **Use the k3s/drum outage as an executable acceptance case.**

The compact architectural summary is:

> **A records what happened. W records what remains to be corrected or
> dispositioned. R establishes what was learned and whether the
> resulting obligations and controls reached an evidenced fixed point.**

And the governing runtime principle is:

> **Detection != Declaration != Mitigation != Recovery != Remediation !=
> Verification. Every distinction must be constructible, reachable,
> observable, and coverable.**

------------------------------------------------------------------------

## References and source notes

The following sources support the external-practice comparisons. The
Nemik implementation observations above are based on the repository
survey and prior discussion summarized in this document; waypoint
references are retained as supplied in the outline where noted.

### ITIL

-   PeopleCert, [ITIL 4 Practice: Incident
    Management](https://www.peoplecert.org/browse-certifications/it-governance-and-service-management/ITIL-1/itil4-practices-incident-management-3684).
-   PeopleCert, [ITIL 4 Practice: Problem
    Management](https://www.peoplecert.org/browse-certifications/it-governance-and-service-management/ITIL-1/itil4-practices-problem-management-3688).
-   AXELOS, *ITIL Foundation, ITIL 4 Edition* (2019), [PDF
    copy](https://www.abim.go.ug/sites/files/%28ITIL%29%20Axelos%20-%20ITIL%20Foundation%204%20edition-Axelos%20%282019%29%5B1%5D.pdf).

### Google SRE and IMAG

-   Google, [Incident Management at
    Google](https://google.github.io/building-secure-and-reliable-systems/raw/ch17.html).
-   Google SRE, [Incident Management
    Guide](https://sre.google/resources/practices-and-processes/incident-management-guide/).
-   Google SRE Workbook, [Postmortem Culture: Learning from
    Failure](https://sre.google/workbook/postmortem-culture/).
-   Google SRE Workbook, [Incident
    Response](https://sre.google/workbook/incident-response/).

### FEMA / ICS

-   FEMA, [Incident Command System Review
    Document](https://training.fema.gov/emiweb/is/icsresource/assets/ics%20review%20document.pdf).
-   FEMA, [NIMS Management
    Characteristics](https://emilms.fema.gov/_is0700b/groups/203.html).
-   FEMA, [ICS Chain of Command and Span of
    Control](https://emilms.fema.gov/_is_0200c/groups/242.html).
-   FEMA, [ICS
    Forms](https://training.fema.gov/emiweb/is/icsresource/icsforms/),
    including ICS-214 (Activity Log) and ICS-221 (Demobilization
    Check-Out).

### Prometheus

-   Prometheus documentation, [Alerting
    Rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/).
-   Prometheus documentation,
    [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/).

### Nemik and fleet references named in the supplied outline

-   `mtools:W2410` --- writer namespaces.
-   `nemik:W2166` --- reader/rank/witnesses/pacing reference in the
    outline; not present in the surveyed Nemik `main` snapshot at W2164.
-   `luthen-observability:W2609` --- alert monitor, A-card minting,
    umbrella lookup.
-   `mtools:W2409` --- fleet census of tick-waits.
-   `luthen-observability:W2600` --- held-execs producer truthfulness
    requirement.
-   `luthen-observability:W2602–W2608` --- btrfs, btrbk, bees panels and
    forecasts.
-   `luthen-observability:W2564` --- re-land identified as the driver in
    the worked example; causal role requires explicit classification.
-   `W2593–W2601` --- action items under the k3s/drum postmortem
    umbrella in the outline.
-   `W2595` --- gate deadlock exposed by the worked example.
-   Nemik surveyed snapshot: W2164, commit `e496230171b7`, 2026-11-13
    12:25:48 UTC.

**Verification note:** External references establish the prior-art
concepts, not the state of the user's repositories. Repository waypoint
claims should be checked against the relevant current revisions before
being treated as implemented facts.
