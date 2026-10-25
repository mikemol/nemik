# The retrospective ritual against the card model

Asked by the operator (host 695f3e0a line 92817, uuid 401fe800-bcb3-46ad-9ceb-98bf7ab0e3ba): present nemik with the
retrospective ritual and audit for workflow integration opportunities. The ritual is
`~/.claude/skills/retrospective-ritual/SKILL.md`: ten gates, G0 precommit to G9 escalate. This is the audit; the gaps are
cards (W982 to W985), and where it overlaps the evidential audit it is folded into W905.

## What exists

Nine of the ten gates have a SHACL shape over a `nemik:Retro` node (shapes.ttl, vocabulary in nemik.ttl), each with a
test on a fixture graph: G0 `RetroPrecommitShape`, G1 `RetroTimelineShape`, G2 `RetroDeltaShape`, G3 `RetroRootShape`,
G5 `RetroBlamelessShape`, G6 `RetroSustainShape`, G7 `RetroFindingShape`, G8 `RetroHandoffShape`, G9
`RetroEnforcementShape`. G4 (decorrelate) has no shape.

## Which gates the card model can witness

| Gate | What the record already holds | Witnessable? |
|---|---|---|
| G0 precommit | the card's next step and witness at mint time, copied into the retro | yes: the ledger line of the mint is the baseline |
| G1 freeze | the ledger lines, hashed (`frozenTimeline`) | yes: write-once by content hash |
| G2 delta | the done claim against the card's witness | yes, mechanically, when the card has a witness; a card with none has no delta to compute |
| G3 trigger, root, contributing | three fields, required and distinct | presence and non-equality only; whether the root is a root is a judgement |
| G4 decorrelate | nothing | no shape: needs the pass chain (W983) |
| G5 blameless | a lexical check on the cause text | weak: a character flaw in new words passes |
| G6 sustain | a required non-empty field | presence only |
| G7 commit | a finding must name a card or a `--certify` verdict change | yes, and an owned card carries a witness |
| G8 fixpoint, handoff | the instrument, channel and operator slots | the slots, not the fixpoint across passes (W983) |
| G9 escalate | `enforcementLayer`, `recurring`, `oneOff` | the layer is declared by the retro, not measured (W985) |

## The gap that matters most

The shapes judge fixtures. Nothing reads a real retro into the graph: the adapter has no source of `nemik:Retro` nodes,
so no retro has ever been judged by them. The shape set is the cheap part; the missing part is ingestion (W982).

## Gaps, carded

- W982: ingest retro records from a durable file into the graph, so the nine shapes judge real retros.
- W983: a shape for G4 and the G8 fixpoint over the pass chain: each pass's findings disjoint from the union of the
  frozen earlier ones, the last pass empty, the handoff labelled exhausted and not verified.
- W984: triggers. A retro stub, seeded with the card's precommit, opens on a gate refusal, a reopened card (done back
  to open), an incident alert clearing, and a ruling that corrects a session. The first two are in the queue's own
  history; the last two need the alert and the transcript.
- W985: G9 as a measured fact: the recurring failure classes of the fleet's retros by the layer their measure lives at
  (memory, instructions, trigger, hook, gate), seeded with the host's four classes of this week (relayed claims not
  checked against the record, sessions idling with ready work, wall-clock-decided gates, paraphrase cited as the
  operator's words), each placed by what actually enforces it now.

## The record form (W982, agreed with mtools-ad, mtools:W1918)

A retro is a separate list, `retros`, beside `waypoints` in the queue document; never a card field. Ids are
`<repo>:R<n>`, drawn from a `retro_counter` of their own that only rises (like a waypoint symbol, never reused). Field
names are snake_case like the cards' (`blocked_on`), and the adapter maps each to the vocabulary's camelCase property:

- a retro: `id`, `card` (the cite reviewed), `trigger`, `root`, `contributing` (list), `precommit`, `frozen_timeline`
  (the hash), `delta`, `sustain` (list), `enforcement_layer` (memory, instructions, trigger, hook or gate), `recurring`
  and `one_off` (booleans), `findings`, `handoff`.
- a finding: `finding_card` (a cite) with `finding_owner`, `due` and `finding_witness`, or `certify_change` alone.
- a handoff: `instrument`, `channel`, `operator` (`self` or `other`).
- the link back: the action card carries `caused_by: <retro id>`, so it is checkable from either side. A finding's card
  that names no such `caused_by` is a Warning, and the owner and due date live on the finding, since cards carry none.

## Spoken but not persisted: where the ritual's anchors detect it

The operator's second ask (this session, 2026-10-24, after host 695f3e0a lines 94427, 94516 and 94534): the
commitment-debt ledger (github:W44) is the retrospective ritual applied to speech, and the ritual's
structural anchors are what let a statement that was only said be told apart from one that was persisted.
Statements are encouraged ("I still need to X"); the debt is the statement with no persisted follow-through.

| Ritual anchor | What it detects in speech | In the ledger and nemik |
|---|---|---|
| G7 COMMIT: a finding ends in an owned, dated, verifiable action item or a checkable verdict change, or it is theater | an "I still need to X" with neither is exactly a finding that terminates in neither | `resolved_by {card, stack, evidence}` is G7's two terminations; open means unattached. nemik counts only the open rows (W1007) |
| G1 FREEZE: a write-once record of what happened | the statement itself is the frozen record | a row's `session`, `line`, `uuid` and `at` are the anchor; the statement is never reworded or removed to clear the debt |
| G0 PRECOMMIT: the expectation before the action | "I will X next" is a precommit; with no card it has no baseline to measure a delta against | W1008: a statement that names a card whose evidence is no newer than the statement; the card's next step and witness are the persisted precommit |
| G5 BLAMELESS | self-criticism as affect ("I keep forgetting", "that was sloppy") is the failure mode the skill replaces with the ritual | RetroBlamelessShape already holds the wording list; the same list is a second sensor over transcripts, and the response is to open a retro stub, not a card against a character trait (W984) |
| G8 HANDOFF | "this needs external review" as prose, not a filled instrument, channel and operator slot | RetroHandoffShape; prose of that form in a transcript is an unpersisted handoff |
| G9 ESCALATE: a recurring class parked below the hook layer is coverability residue | "said it was undone, did not persist it" recurs, so it must not sit at memory or instructions | placed by what enforces it now: the loop prompt line (instructions), mtools' Stop hook (hook), the open-commitment ratchet on the pace board (gate, W1007): the three layers, and the last is the first one that cannot be skipped (W985 records the class) |

So a ledger row is a retro finding awaiting its G7 termination, and the retros list agreed with mtools (W982)
can hold it: `finding_card` with owner, due and witness is the persisted termination. Two things follow that
are not yet built: the transcript sensor for G5 wording and for prose handoffs (mtools' extractor, W1931, would
carry them as further row kinds), and the retro stub (W984) opening from an unattached row that stays open
past the learned bound.

## What is not claimed

The audit read the shapes, their vocabulary and the existence of tests; it did not run them against a real retro,
because there is none. G3's split and G5's blamelessness stay judgements a shape can only bound.
