# Every channel the fleet uses to say something to a peer, and its ActivityPub analogue (nemik:W917, W915)

The operator asked (2026-10-23) that nemik's communications stay aligned with the federated,
ActivityPub-aligned model. This is the inventory half of that audit: which channels exist, how each
names things, and what each would be in ActivityPub terms. Whether `outbox.py` matches the ActivityPub
Recommendation and ForgeFed is W916, which needs the specs read; I have not read them for this
document, so the ForgeFed terms below are the ones `outbox.py` and `federation.md` already use, not a
check against the standard. Marked **(code)** when I read it in the source and **(mine)** for a
reading.

ActivityPub in one paragraph, as the baseline: an **actor** has an **inbox** and an **outbox**;
**activities** (Create, Update, Offer, Accept, Resolve...) with an `actor`, an `object` and a stable
`id` are **delivered** to other actors' inboxes (HTTP POST, signed) and published in the outbox;
actors and objects are named by dereferenceable HTTP IRIs. Federation is the property that no server
is special: any server that speaks the protocol can deliver to any other.

## The identity every channel shares

A workstream is `urn:nemik:<repo>` and a card is `urn:nemik:<repo>/W<n>` (`adapter.BASE`) **(code)**.
These are URNs: stable and unique, but not dereferenceable, so no peer can fetch an actor or a card
from its name. In letters and prose the same card is `repo:W<n>`. ActivityPub wants http(s) IRIs for
actors; this is the first gap, and it touches every row below.

## The channels

| # | Channel | Writer, reader | Identity of a message | ActivityPub analogue | Federable as it is? |
|---|---|---|---|---|---|
| 1 | **Queue edges**: `blocked_on`, `enables`, `caused_by` in each repo's `paths-forward.json` | one writer per repo; nemik reads every queue (`nemik-inbound`, the graph) | `repo:W<n>` in the field | a dependency between tickets of two actors, pulled by the reader | Pull only: a peer's waiting is visible to the owner only when nemik reads both queues. |
| 2 | **Inbox letters**: `<repo>/inbox/<date>-<slug>.md`, header `From: x (W9)` and `To: a` | a session or a human writes the file into the peer's inbox directory; `nemik-inbound` and `nemik-check --letters` read it | the file path | an activity delivered to an actor's inbox | The place is right (a per-actor inbox) and the transport is a file copy on one host. No activity type, no `id` but the path, no signature. |
| 3 | **Edge letters**: `<date>-nemik-edge-<repo>-<W>-<kind>-<W>.md`, one per cross-repo edge of a closed card, once, recorded in `.nemik-delivered` | `nemik.delivery` and `witnesses.deliver` write them into the waiting repo's inbox | the file name carries the edge | an `Update` or `Resolve` of a ticket, delivered to each dependant's inbox, deduplicated by activity id | The closest to an activity: one per edge, idempotent through the record. It carries the edge kind in its name and prose, not as a typed activity. |
| 4 | **Witness letters**: `nemik-witness-<repo>-<W>.md` | `witnesses.wake` when a witness holds | the file name | an activity from the witness (an `Update`) to the waiting actors | Same route as 2 and 3. |
| 5 | **Floor asks**: summit's `floor/inbox/<slug>.bib`, `kind=ask by=<filer> to=<owner>` | `nemik-ask` writes it, summit validates it | the slug | an `Offer` addressed to the owner | The form is summit's own BibTeX-like entry, not JSON-LD. |
| 6 | **Exports**: `.claude/paths-forward.export.json` v2 per repo, copied by luthen to the host export tree | the repo's writer, luthen, `nemik-exports` | repo and symbol | the actor's published collection; "withheld" is its visibility | A pull of a document, not a stream. |
| 7 | **The outbox**: `outbox/<repo>.jsonld`, an `OrderedCollection` of `Offer`, `Accept` and `Resolve` of a `Ticket` | `outbox.py` from the queue graph, served by `nemik-serve` | the card IRI (a URN) | the actor's outbox | **The only channel already in the model**, read-only by design: "nothing is delivered" (`outbox.py`). It carries no dependency edges and no actor document. |
| 8 | **OSLC TRS**: base and change log (`trs.py`, `catalog.py`) | nemik serves it | the resource IRI and the change log position | outbox paging, in a different standard | Pull, with a cursor. |
| 9 | **Session messages** (Claude Code's cross-session send) | one agent session to another, on one host | a message id the tool returns | a direct message to an actor | Not nemik's, transient, and the receiving session may never read it; the fleet's rule is that anything durable goes in a card or a letter. |
| 10 | **The log service**: OTLP log records in VictoriaLogs (mikemol-commit's landing records, `waitemit`'s per-pair records, the host-root frontier stream, mtools' `mikemol.waypoint.event`, and estate's proposed verdict line) | the emitting tool writes through `mikemol.otlp`; nemik reads on the host (`endpoint.vlogs_lines`, `nemik-hostroot --landings`) | a record's timestamp and its attributes (`service.name`, labels); no id of its own | an activity published to an actor's outbox, read by pull | **Not yet in the model, and already a channel**: see "The log as a channel" below. |

## What the measurement shows (mine, from the files)

1. **Most of the traffic is one-to-one files on one host.** `nemik/inbox` holds 42 letters; 22 of them,
   all dated 2026-10-23, are edge letters nemik wrote that day (`pendingdeliver`, W889). Every one is
   a message to an actor's inbox in the right place, and none is an activity a different server could
   receive: there is no type, no `id`, no `actor` IRI and no signature.
2. **The one channel in ActivityPub form (7) says less than the letters do.** The outbox shows a
   card's state as a verb on a `Ticket` and nothing of its edges, while the edges are what the letters
   (3) and the queue (1) exist to carry.
3. **Delivery is the operator's boundary, on purpose.** `outbox.py` says an inbox, a signature or a
   push to another server "crosses nemik's read-only boundary and is the operator's decision". A
   change that keeps channels 2 to 5 federable has to stop short of delivery or ask for it.
4. **Letters cost the receiver attention.** An uncited letter is an `UNCLAIMED` row in the receiver's
   next `nemik-inbound` until a card cites it (six appeared in nemik's own on 2026-10-23). A federated
   inbox has the same problem and answers it with typed activities a client can filter; the letters
   have none.

## The log as a channel: how it could mate with the federated model (mine)

The operator raised this audit because of a proposal to pass communications through the system log
(estate's leaning, estate:W39: ship the waldo's verdict line to the log service, not to a file) and
said he cannot tell whether that is wrong, only that it needs mating with the federated model. Read
against ActivityPub, it is not wrong, and it is not yet mated either:

**What fits.** An outbox is an ordered, append-only collection of activities an actor publishes, and
a consumer may read it by pull (polling the collection is allowed; push delivery is the other mode).
A log store is an ordered, append-only, timestamped, queryable record stream with attributes: as
storage for an actor's outbox it is natural. The records are already how several tools speak to
nemik today (channel 10), so the question is a shape, not a new route.

**What is missing, each a gap against the model.**

1. **An activity, not a line.** A record's body should be one ActivityStreams activity: `type`,
   `actor`, `object`, `published`, and a stable `id`. Today a record has a timestamp and attributes;
   its identity is its position in a query.
2. **An actor IRI for the writer.** `service.name` names a tool; the actor is the workstream
   (`urn:nemik:<repo>`, and eventually an http IRI). The record should say which.
3. **A way to be read as a collection.** An outbox is a collection with an IRI. A LogsQL query is
   the collection; nemik-serve could expose it as `outbox/<repo>.jsonld` (channel 7), so a log-borne
   verdict or landing appears beside the card activities and a federated reader needs only the
   outbox. This is the join between channels 7 and 10.
4. **Addressing.** A log has no recipient: anyone who can query reads everything the query matches.
   In ActivityPub the `to` and `cc` of an activity say who it is for. A record that is for a peer
   needs that in the body, and the reader's inbox is then a standing query, not a directory.
5. **Authorship.** Any process that can write to the log can write a record under any `service.name`;
   ActivityPub signs. Without a signature the log is a claim, not a proof, which is the weakest rung
   of docs/toulmin-map.md: a record can be grounds for a witness but should not be a warrant.
6. **Retention and loss.** A log can rotate, drop or thin records; an outbox is expected to be a
   stable collection. A channel that closes cards must either keep what it relies on or say that
   absence is not a verdict (nemik's witnesses already treat "could not observe" as not done).

**The mating, as a rule (mine).** A log record that crosses between workstreams is an ActivityStreams
activity in its body, named by an id, attributed to an actor IRI, addressed in the body, and exposed
to a federated reader as a collection by nemik's outbox. Nothing else about the log has to change.
A tool that emits a record to itself (a metric, a trace) is not a communication and is not covered.

## What this does not do

It does not check the verbs against ForgeFed (W916), and it does not recommend changes (W918). It
fixes what has to be kept federable: the six places an identity, an activity type or a delivery
could be added without breaking a reader, which are the actor IRI (every row), a typed activity and
an `id` on a letter (rows 2 to 4), the dependency edges in the outbox (row 7), and a form for an ask
that is not summit-only (row 5).
