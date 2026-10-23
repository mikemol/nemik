# nemik's outbox against ActivityPub and ForgeFed (nemik:W916, W915)

The first part of the federation audit: nemik's ForgeFed outbox (`src/nemik/outbox.py`, W354) read
against the two specifications it names. `docs/federation.md` said "I have not read ForgeFed's card
model"; this reads it. `docs/federation-channels.md` (W917) is the inventory of channels.

## Sources, and how they were read

- **ActivityPub**, W3C Recommendation, 23 January 2018 (Social Web Working Group),
  https://www.w3.org/TR/activitypub/ .
- **ForgeFed**, a branch snapshot dated 18 June 2025 (branch `fix`, commit c35fe68), editor Pere Lev;
  the spec says of itself "still under construction", https://forgefed.org/spec/ .

Both were read through a fetch tool that answers a question against the page with a small model, so
the section numbers and quotations below are that tool's reading, not mine of the text. ForgeFed's
page is 522,819 characters and I read the first 200,000. **The vocabulary half was then read
directly** (W921, 2026-10-23), from the spec's own source, `spec.bs` on Codeberg
(ForgeFed/ForgeFed, branch `main`, 508,054 bytes, last commit 2025-08-21, 192fa564): the fetch tool's
later chunks never reached it. The definitions below marked **(source)** are from that file. Still
not read: the behaviour sections for the actors other than TicketTracker's dependency handling.

## What the standards say that bears on nemik

ActivityPub:

- An actor MUST have an `inbox` and an `outbox`, each an `OrderedCollection` (§4.1).
- Identifiers must be publicly dereferenceable URIs, "such as HTTPS URIs", under the originating
  server's authority (§3.1). URNs are not mentioned; a URN is not dereferenceable, so by that rule it
  does not qualify (my inference).
- Delivery is an HTTP POST of the activity to each recipient's inbox (§7.1); authentication is left
  open ("no strongly agreed upon mechanisms", §B.1). Reading an outbox by GET is allowed (§5.1): a
  pull is a federation mode.
- `bto` and `bcc` are stripped before delivery but used to pick recipients (§6). `published` is not
  required, and an outbox activity's `actor` is not listed as mandatory.

ForgeFed:

- Tickets live at a **`TicketTracker`** actor; other actor types include `Repository`, `Project`,
  `Team`, `Organization` (§3.1).
- **`Offer`** of a `Ticket` is the author asking a tracker to open it (target: the tracker);
  **`Accept`** is the tracker telling the author the ticket now has an id; **`Reject`** is the
  tracker refusing; **`Resolve`** is sent by a person with triage access to the tracker to close the
  ticket, and the tracker replies with an `Accept` (§3.7.1, §3.7.5). A ticket's open or closed state
  is the property `isResolved` (with `resolvedBy` and `resolved`), not an activity.
- A `Ticket` offered for opening needs `summary`, `attributedTo`, and `content`; `context`, if given,
  must equal the Offer's target (§3.7.1).
- **The vocabulary** **(source)**. `Ticket` extends ActivityStreams `Object`: "an item that requires
  work or attention ... in the context of a project". Its own properties: `assignedTo` and
  `assignments`, `isResolved`, `resolvedBy` and `resolved` (also on `Milestone` and `ReviewThread`),
  `ticketMilestone`, and four for dependencies: **`dependsOn`** (tickets this one cannot be resolved
  without, not functional, inverse of **`dependedBy`**) and the collections **`dependencies`** and
  **`dependants`** (each a functional `Collection` of `TicketDependency`; "often called reverse
  dependencies"). `TicketDependency` extends `Relationship`: it MUST specify `subject`, `object` and
  `relationship`, and `relationship` MUST be `dependsOn`; the spec's example is an object with an `id`,
  `attributedTo`, `summary` and `published`. The spec's own JSON-LD examples for `dependsOn`,
  `dependedBy`, `dependencies` and `dependants` are still "TODO".
- **Dependencies** (§3.9, §3.9.1): the author of a dependency, with triage access to the parent
  tracker P, sends an `Offer` to both P and the child tracker C, with target P and as its object a
  `TicketDependency` (subject: the parent ticket, relationship `dependsOn`, object: the child ticket),
  carrying a capability `Grant`. P validates it, adds it to the parent ticket's dependencies
  collection, and replies with an `Accept` whose result is the new dependency; C, seeing both, adds it
  to the child ticket's **dependants** collection. "Doesn't require consent of both sides": only the
  parent's side consents.

## What `outbox.py` does, against that

| Matter | Standard | nemik today | Verdict |
|---|---|---|---|
| Actor has inbox and outbox | MUST (§4.1) | an outbox collection per repo (`outbox/<repo>.jsonld`); no inbox collection; no actor document | Half. |
| Identifiers | dereferenceable http(s) URIs (§3.1) | `urn:nemik:<repo>` and `urn:nemik:<repo>/W<n>` | Does not meet it. Needs a published base URL, which is the operator's to give. |
| Actor type | a `TicketTracker` holds tickets; a `Repository` is another actor | the workstream is typed a "ForgeFed actor" with no ForgeFed type | Missing: the right pair is a `TicketTracker` per queue (and a `Repository`). |
| Ticket properties | `summary`, `attributedTo`, `content`, `context`, `isResolved` | `summary` only | Thin. A done card carries no `isResolved`, a card no `context` (its tracker). |
| State | the `isResolved` property | the state as a **verb**: ready or blocked is `Offer`, working is `Accept`, done is `Resolve` | **Misuse.** In ForgeFed these are requests with senders: `Accept` is a tracker accepting a submitted ticket, not "someone took it on". Only `Resolve` is near, and it is a person's act on the tracker, not a state label. |
| Dependencies | `Offer` of a `TicketDependency`, recorded in the parent's dependencies and the child's dependants | none in the outbox; the edges live in the queue (`blocked_on`, `enables`) | **Absent.** |
| Delivery | HTTP POST to an inbox | none, by decision ("an inbox, a signature or a push ... is the operator's decision", `outbox.py`) | A choice, kept. |
| Pull | a GET of an outbox is a mode | served by `nemik-serve` | Present. |

**One match worth keeping.** ForgeFed records a dependency on **both** sides, in the parent's
dependencies and the child's dependants, and the child's side is made by the child's tracker seeing
the offer. nemik's `UNCLAIMED` inbound row is the same fact: a card in repo B has said it waits on
repo A's card, and A has no card that records the dependant yet. The two vocabularies describe one
structure, and the outbox could carry it.

## What follows for W918 (recommendations, mine)

1. Say a card's state as `isResolved` and `context` on the `Ticket`, not as a verb. Keep the verbs
   for events: a real `Resolve` when a card is closed (an edge letter, W889, is one), an `Offer` when
   a card is minted.
2. Carry the edges, the lighter way first. A read-only outbox runs no tracker handshake, so the
   `Ticket` object can say it itself with the vocabulary's `dependsOn` (for `blocked_on`) and
   `dependedBy` (for `enables`), each a list of ticket identifiers, with no `Offer` needed; a real
   `Offer` of a `TicketDependency` (subject, `dependsOn`, object, to both trackers, then the parent's
   `Accept`) is the form for a delivered edge, and delivery is the operator's. Checked against the
   source now: both forms are defined and consistent with §3.9.1.
3. Type the actors: a `TicketTracker` per repo's queue, with an http(s) IRI. That needs a base URL.
4. Leave delivery alone: a POST to an inbox crosses the operator's boundary.
5. The log as a channel (W919, in `federation-channels.md`) uses the activity form drafted there.

## What this does not settle

The first version of this document had not read ForgeFed's vocabulary; it has now (W921). Whether ForgeFed's capability `Grant` has any counterpart in a read-only
outbox was not looked at. And the standard is a draft: the verbs above can change.
