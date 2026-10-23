# What to change to keep nemik's communications federable (nemik:W918, W915)

The last part of the federation audit the operator asked for (2026-10-23: nemik's communications
aligned with the federated, ActivityPub-aligned model). It rests on the inventory
(`docs/federation-channels.md`, W917) and on the outbox read against the specifications
(`docs/federation-audit.md`, W916, W921, with ForgeFed's own source). Each recommendation is a card,
says which channel it keeps federable, and says what a session could then check or reason about that
it cannot today. Marked **(mine)** where it is a judgement. Delivery stays the operator's decision
throughout, as `outbox.py` says: nothing here sends anything to another server.

## The recommendations

**R1. State as a property, verbs for events** (W939). The outbox says a card's state as a verb on a
`Ticket` (ready or blocked is `Offer`, working is `Accept`, done is `Resolve`). In ForgeFed those verbs
are requests with senders and a ticket's state is `isResolved`. The `Ticket` should carry
`isResolved`, `resolved` and `context` (the tracker it lives in), and the verbs belong to real events
only (a card being minted, a card being closed).
*Keeps federable:* the outbox (channel 7). *A session could then:* tell "this card is closed" from
"this card was just closed", and a federated reader would read it as the standard does.

**R2. Edges on the ticket** (W940). The outbox carries no dependencies. A read-only outbox needs no
handshake: each card's `blocked_on` is `dependsOn` and each `enables` is `dependedBy` on its `Ticket`,
as lists of ticket identifiers (ForgeFed defines both and their inverse; a delivered edge is the
`Offer` of a `TicketDependency`, which is the operator's boundary).
*Keeps federable:* queue edges (channel 1) through the outbox. *A session could then:* read what a
card waits on, and what waits on it, from one document, including the cross-repo edge the letters
exist to carry; the `UNCLAIMED` inbound row becomes a `dependedBy` the owner's outbox lacks.

**R3. Actors an outsider can fetch** (W941, an operator decision). Actors and cards are URNs
(`urn:nemik:<repo>`); ActivityPub wants dereferenceable http(s) URIs, a `TicketTracker` actor per
queue, and an `inbox` and `outbox` on each actor. This needs the one thing nemik cannot supply:
the public base URL under which the pod is reachable, and whether to serve an inbox that accepts
nothing (refusing a POST) or none. *Keeps federable:* every channel's identity. *A session could
then:* cite a card as a link a peer or a federated client can open, not as text.

**R4. A typed envelope on edge letters** (W942). An edge letter is a file whose name and prose carry
the edge. It should also carry, in a machine-readable block at its head, one activity: a `Resolve` (or
`Update`) with an `id`, an `actor` (the closing card's workstream), an `object` (the card) and a
`target` (the waiting card), the same fields a federated inbox would receive. The prose stays.
*Keeps federable:* inbox letters, edge letters, witness letters (channels 2 to 4). *A session could
then:* filter its inbox by type instead of reading every letter (the `UNCLAIMED` rows that cost
attention), and deduplicate by `id` as ActivityPub does.

**R5. The log record as an activity** (W919, already carded). A record that crosses between
workstreams has an ActivityStreams activity in its body, with an `id`, an `actor`, a `to`, and is read
as a collection through the outbox. *Keeps federable:* the log (channel 10). *A session could then:*
read estate's read-back verdict as a federated activity, and close a card from it.

**R6. A floor ask that is not summit-only** (W943, last). Floor asks (channel 5) are summit's
BibTeX-like entry. An `Offer` addressed to the owner, in the same JSON-LD as R4, beside the entry,
would let the ask travel without summit's tool. *A session could then:* file an ask a peer outside the
fleet could read. Lowest value of the six, because no peer outside the fleet exists today (mine).

## What is deliberately not recommended

- **Delivery.** No POST to another server, no HTTP signatures, no WebFinger: all cross the read-only
  boundary and need the operator's decision and a threat model (ActivityPub leaves authentication
  open, §B.1).
- **Replacing the queue edges.** The queue stays the source; the outbox and letters are views of it.

## Order

R1 and R2 are changes to one module (`outbox.py`) with tests against the standard's own fields, and
are first; R4 and R5 follow; R3 waits on the operator; R6 last. nemik's rank orders them with the
rest of the queue.
