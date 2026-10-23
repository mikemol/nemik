# What the card model and its PROV and OSLC export can say (nemik:W906, W905)

The first part of the evidence audit: the codomain, meaning every term the language can express
today, with its type and who may write it. It was made from the code (`src/nemik/adapter.py`,
`data/nemik.ttl`, `data/shapes.ttl`, `warrants.py`) and from a count over the fleet's queues on
2026-10-23: 9,410 cards in 18 queues (6,793 done, 2,382 blocked, 229 ready, 6 working). The
operator's request is the one sentence on W905's first warrant (host 695f3e0a line 91539); the
Toulmin map is W907 and the standards are W910 and W911.

## 1. The card as the writer stores it

`mikemol-paths-forward` is the only writer (the loop's rules forbid a hand edit); nemik reads. A card carries these fields. The count is how many of the 9,410 carry it.

| Field | Type | Cards | What it says | Who writes it |
|---|---|---|---|---|
| symbol | str `W<n>` | 9410 | identity, never reused | writer, at `--add` |
| title | str | 9410 | the claim the card makes: what it is for | writer, `--add`, `--update --title` |
| status | ready, blocked, working, landed, done | 9410 | lifecycle step | writer, `--update --status` |
| enables | list of symbols | 9410 | this card unblocks those | writer, `--enables`, `--add-enables` |
| blocked_on | list of text | 9410 | what it waits on (section 2) | writer, `--blocked-on` |
| blocked_kind | agent, human, null | 9409 | who must act | writer |
| touches | list of tags | 9410 | areas, and `file:<path>!w` leases | writer, `--touches` |
| next_bounded_step | text or null | 9410 | the next action, in prose | writer, `--next` |
| evidence | text or null | 9410 | **everything that supports a closure, one free-text field, appended** | writer, `--evidence-append` (and `--evidence-redact`) |
| issued_at, last_worked, completed | stamps | 9410, 9410, 7621 | when | writer |
| ticks_blocked | int | 9410 | loop ticks spent blocked | writer |
| minted_during, caused_by | tick or interrupt, text | 8566 | what started the card | writer, `--caused-by` |
| vector, vector_source | WV:1 text, default or signal or agent | 2665 | priority | writer |
| weight | int | 1528 | rank position | writer, `--weights-from` |
| manifest, size_class | files, small or medium or large | 1259, 1241 | planned edits and size | writer |
| warrants | list of JSON-LD | **122** | a transcript record standing for an operator ruling | writer, `--warrant` |
| witness, witness_lang | Rego or PromQL text | 60, 23 | a query that, when it holds, closes the card | writer, `--witness` |
| attachments | list of path and sha256 | 8 | a file cited as evidence, hash-pinned | writer, `--attach` |
| landed, landed_at, deploys | text, stamp, bool | 26, 2, 4 | the commit, the stamp, whether landing is the end | writer |
| withheld | bool | 3 | not published by the pod | writer, `--withheld` |
| reference_arm, population, command, deferred | text, dict | 16, 16, 4 | realizability facts | writer, `--admit` |
| dtstart, due, alarms, location, rrule | RFC 5545 | 3, 4, 5, - | dating | writer |
| done_evidence, rank_reason, why_it_matters, parent, legacy, note, body, status_note | text | 16, 86, 18, 33, 19, 10, 9, 6 | older or ad hoc prose | writer or hand, historic |

Statuses count: done 6,793, blocked 2,382, ready 229, working 6. `blocked_kind` is null on 6,990
cards, agent on 2,298, human on 122.

### The free fields

Beyond the table, 180 of the 223 distinct keys appear on four cards or fewer, and 103 of those
carry a date in the name (all from 2026-09-21 to 09-26, the fleet's first week): `ruling_2026_09_21T18_17Z`, `operator_ruling_2026_09_24`, `ruling_k_implemented`,
`key_finding`, `decision_taken`, `measured_2026_09_26`, `defect_found_2026_09_22`,
`blocker_was_wrong_2026_09_23`, `peer_framing_2026_09_22`, `open_for_operator` and so on. They are
claims, rulings, measurements and corrections that a session wrote as a new field, because the model
had no typed place for them. None is read by nemik's adapter, so none is in the graph.

## 2. The forms of `blocked_on`

A free-text list, resolved by nemik (`nemik:waitsFor`) to one of: a local symbol `W<n>`; a foreign
card `repo:W<n>`; a workstream name; `operator: decide <question>` or `operator: act <command>`
(bare `operator` is a defect: "no ask stated"); `cal:<label>/<uid>`; `host:<id>`; and
`nemik-witnesses` for a witnessed card. A value that resolves to none of these is
`nemik:unresolvedBlocker`.

## 3. What the export says

The adapter turns each card into an `oslc_cm:ChangeRequest` (OSLC Change Management) with
`dcterms:identifier`, `title`, `subject` (the touches), `created` and `oslc_cm:state`, `closed`,
`closeDate`. Everything else is in nemik's own namespace (`nemik.ttl` has 89 subjects: classes, properties and
concepts): the
relations (`enables`, `blockedOn`, `waitsFor`, `blockedKind`, `acceptableSupplier`), the plan
(`plannedPath`, `sizeClass`, `editsFile`, `namesFile`, `hasNextStep`), the clock (`lastWorked`,
`ticksBlocked`, `landedAt`), and derived facts a shape reads (`claimsRuling`, `malformedWarrant`,
`allBlockersLanded`, `readyBehindOpen`, `unclaimedBlockOn`, `operatorAsk`).

PROV-O is used in three places only:

1. `prov:wasInformedBy` from a card to the card named in `caused_by`.
2. A ledger line becomes a `prov:Activity` with `startedAtTime`, `prov:used` the card it names, and
   `prov:wasAssociatedWith` a `prov:Agent` (the writing session as `urn:uuid:`, or the operator).
   `nemik:kind`, `effortClass`, `outcome` and `mechanism` carry the line's columns.
3. A warrant, as the writer stores it, is a JSON-LD entry read in as PROV: `prov:wasDerivedFrom` an
   entity (the transcript record), and WarrantRecordShape asks of that record a
   `prov:generatedAtTime`, a `prov:wasAttributedTo` a `prov:Agent` (the operator is
   `urn:nemik:operator`) and a `prov:wasGeneratedBy` an activity.

A retro (`nemik:Retro`, `RetroFinding`, `RetroHandoff`) is a separate small vocabulary with
`precommit`, `root`, `contributing`, `sustain`, `delta`, `enforcementLayer`, `recurring` and
`oneOff`. The writer's newest warrant flags, `--claim` and `--reason` (mtools:W1860), are not yet
read: how they are stored in the JSON-LD was not checked for this document.

## 4. What this shows

Measured, not argued:

1. **Evidence is one text field.** All 9,410 cards have `evidence`; it holds quotes, measurements,
   commit hashes, peers' statements and the card's own inferences side by side, in prose, appended.
   The graph holds none of it: the adapter reads `evidence` for letters and a few phrases only.
2. **A warrant is a record, not a rule.** Only 122 cards (1.3%) have one, and what it points at is
   the operator's utterance. Whether the card's step follows from that utterance is not stated
   anywhere: the inference is implicit, in the card's prose.
3. **Rulings are found by phrase.** `UnwarrantedRulingShape` flags an open card that says
   `operator ruling`, `per the operator` and a few more, or (since 7df054b) names the operator, a
   line and a uuid, and has no warrant. It sees words, not a typed claim, which is how estate's
   cards were missed.
4. **There is no field for how sure.** Nothing separates `quoted`, `derived from a quote`, `measured`
   and `my judgment`. The 180 rarely used keys (103 of them dated) look like the model's users
   routing around that.
5. **Nothing can be defeated.** A superseded ruling, a witness that failed, a correction (the free
   fields `blocker_was_wrong_2026_09_23`, `status_corrected`, `warrant_correction`) have no typed
   relation to the claim they correct.
6. **Who wrote a claim is lost.** A ledger line records its session; `evidence` appended by a writer
   call does not say who appended it, or whether the text is the writer's own or a peer's.

W907 maps these onto Toulmin's parts, W910 and W911 survey the standards that already type them,
and W909 recommends the minimum changes.
