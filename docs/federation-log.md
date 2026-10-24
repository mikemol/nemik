# A log record that crosses between workstreams, as a federated activity (nemik:W919, W915)

The operator asked (2026-10-23) that nemik's communications stay aligned with the federated,
ActivityPub-aligned model, and said the proposal to pass communications through the system log "needs
mating with the federated model, somehow". `docs/federation-channels.md` ("The log as a channel")
gives the rule; this document says what it would mean for each writer and for nemik's outbox, and
what it deliberately leaves alone. Marked **(mine)** where it is a judgement; **(relayed)** where it
is estate's word and not read here. Nothing here is built.

## The rule

A log record that crosses between workstreams has, as its body, one ActivityStreams activity:

| Field | What it is | Why |
|---|---|---|
| `type` | the event: `Create` (a card minted), `Resolve` (closed), `Update`, `Offer`, or a verdict's own verb | ActivityStreams names an event, not a state (R1 in `federation-recommendations.md`) |
| `actor` | the workstream, `urn:nemik:<repo>` (an http IRI once W941 is decided) | `service.name` names a tool, not who is speaking |
| `object` | what it is about: a card IRI, or the verdict as a nested object | the thing a reader acts on |
| `published` | when it happened | the record's own time, not the time it was read |
| `id` | stable across a re-send | so a reader deduplicates as ActivityPub does |
| `to` | present only when the record is for a peer | a log has no recipient; the body supplies one |

The record's own attributes stay, so a LogsQL query still works as it does today. The body is added to,
not replaced, and a record that tells only itself something (a metric, a trace) is not covered.

## What each writer would change

**nemik's wait records** (`waitlog.py`, W886; read here). Today a record's body is the sentence
`<waiting card> has waited <n> ticks on <blocker card>` with attributes `waiter` and `blocker`, the two
repos. As an activity it is an `Update` by `urn:nemik:<waiter repo>` of the waiting card, with the
blocker as `target` and the ticks as a note. Its `id` is the pair and the instant
(`urn:nemik:wait:<waiter>/<symbol>/<blocker>/<symbol>/<time_ns>`). The sentence can stay as `content`,
since ActivityStreams carries human text beside the structure. This is the cheapest conversion and a
real test of the shape.

**estate's verdict line** (estate:W39, relayed). The waldo's stdout stays one JSON verdict line and the
shipper wraps it as one record: `type`, `actor` estate, `object` the verdict, `published` the record
time, `id` plan hash plus `published`, `to` when it is for a peer. The same record is what a card's
witness reads, with `fresh_since = published`. Estate's constraint stands: the envelope carries nothing
the waldo scrubbed. Estate builds this; nemik's part is to read it (W914).

**mikemol-commit's landing records** (mtools). The records exist (the landings board reads them). I did
not read their attributes for this document, so I do not say what their body holds. As an activity a
landing is a `Create` of a commit by the repo, with the card it closed as `context`. Whether mtools
wants that is mtools' decision; the rule asks only that a landing that another workstream waits on
be an activity.

## How nemik's outbox serves them

A LogsQL query is a collection. A repo's outbox is its cards' `Create` and `Resolve` activities
(`outbox.py`) and then the log activities that name the repo as actor, in `published` order, as
`orderedItems`. Built (nemik:W947 to W950), with two choices **(mine)**:

- The log is read on the host and the outbox reads a file. nemik-serve never spawns a process, and
  the log is reached through luthen's query tool, so `nemik-hostroot --log-activities` asks the log
  store (service `nemik-waits`) and writes `log-activities.json` as one flat JSON object per line (a
  header with `as_of`, then an activity per line), which the static build reads from beside the
  queues (`serve.LOG_FILE`) and a changed file rebuilds the outboxes. The log remains the source and
  the outbox a view of it, the same relation the outbox has to the queue. An earlier version of this
  document said the collection would be built on request from the store; that cannot hold under the
  no-spawn rule, and the file is how landings and the host-root frontier already reach the page.
- A file that is not there, or cannot be read, makes the log part of the collection absent, and the
  collection says so in a `summary`, instead of returning the cards alone as if they were the whole.
  Absence is not a verdict, which is how nemik's witnesses already read "could not observe". The file
  carries `as_of` but the outbox does not yet refuse a stale one; a stale file shows older
  activities, never invented ones.
- An activity that names a withheld card is dropped, as the cards are.

## What this does not fix

- **Authorship.** Any process that can write to the log can write a record under any actor. An
  activity without a signature is a claim, not a proof: it can be grounds for a witness but not a
  warrant (`docs/toulmin-map.md`). Signing is delivery's problem and stays the operator's decision.
- **Retention.** A log can rotate or thin records. A card that closes on a record must either keep it
  (cite it in `evidence`) or accept that its absence later is not a reversal.
- **Addressing.** A record with no `to` is read by anyone who can query. That is intended for the
  fleet; a peer outside it needs a delivery channel this does not add.

## Cards this implies

- Done: the wait record as an `Update` activity (W944), its reader (W947), the host file (W948, W950)
  and the outbox appending it (W949).
- Reading estate's verdict as the witness record: W914, which waits on estate.

nemik's rank orders them with the rest of the queue.
