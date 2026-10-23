# The card model against Toulmin's argument (nemik:W907, W905)

The second part of the evidence audit. It takes the terms in `docs/evidence-codomain.md` (W906) and
asks, for each of Toulmin's six parts, whether the card model has it, mixes it with another part, or
lacks it. The model of argument is Stephen E. Toulmin, *The Uses of Argument* (Cambridge University
Press, 1958; updated edition 2003): an argument moves from **grounds** (data) to a **claim**, licensed
by a **warrant** (a general rule that the step is allowed), which a **backing** supports; a
**qualifier** says how strongly the grounds support the claim, and a **rebuttal** names the
conditions under which the claim does not hold. Mapping nemik onto it is my reading; where I say a
field is "really" one part, that is an argument, not a fact about the code.

## The map

| Toulmin | What nemik has | Verdict |
|---|---|---|
| **Claim** | `title` (what the card is for); `status: done` (the claim that it is done); a sentence in `evidence` ("W547 done") | Present, but the done-claim is a status flip, not a statement with its own grounds. |
| **Grounds** | `evidence` (free text, appended); `witness` (a Rego or PromQL query over observed facts); `attachments` (path plus sha256); `landed` (a commit); ledger lines (PROV activities); the manifest against the landed diff (`drift`) | Present, in six shapes with six degrees of checkability. Only a witness and an attachment can be re-checked by a machine; the rest is prose. |
| **Warrant** (the inference licence) | Nothing names it. For a witnessed card the witness query *is* the rule "when this holds the card is done", the one place the licence is explicit and executable. Elsewhere it is implicit in `next_bounded_step` | Mostly missing. This is the largest gap: a card says what it rests on, never why that licenses the step. |
| **Backing** (what supports the licence) | `warrants` (122 cards): a transcript record, an utterance of the operator, with its time, speaker and activity (`prov:wasDerivedFrom`, `generatedAtTime`, `wasAttributedTo`, `wasGeneratedBy`); the loop prompt and the standing set (rules the cards cite in prose); mtools' Rego policy | **Conflated.** Our `--warrant` is the operator's utterance: that is grounds for the claim "the operator ruled X", and backing for the standing rule "an operator ruling binds the fleet". It is neither Toulmin's warrant nor kept apart from the card's other grounds. |
| **Qualifier** | No field. Prose: `(relayed, the operator's words not verified by me)`, `UNVERIFIED --manifest` in the proposal, `Warning` against `Violation` for a shape's own severity, `vector_source` (default, signal or agent) for a priority | Missing as data; present as hand-written hedges that no shape reads. |
| **Rebuttal** | No field. A failed witness leaves a card open (rebuttal by absence). Prose and free fields: `warrant_correction`, `status_corrected`, `blocker_was_wrong_2026_09_23`, `reopened_and_reclosed`; a superseding ruling is a new sentence in `evidence` | Missing as relation. Nothing links a correction to the claim it corrects, or a superseding ruling to the one it supersedes. |

## Where the conflation costs something

A measured case: W643's `evidence` (read 2026-10-23) holds, in one string and in this order, a
relayed statement marked "the operator's words not verified by me", the verification of that
statement against the transcript with its line and uuid, a measurement of an AST count, a decision by
a peer session, and several status reports from another repo's session. That is five epistemic kinds
(relayed, verified quote, measurement, peer decision, peer report), each with a different strength and each
open to a different kind of rebuttal, and the model stores them as appended sentences. A check cannot
tell the quote from the report. It found that out the hard way twice this week:

1. The phrase matcher of `UnwarrantedRulingShape` passed estate's W2, W3 and W10, which cited the
   operator's record by line and uuid in words it did not know (W896).
2. github-8f cited a record for a request, and the record turned out to be about another matter: the
   line was a real quote, but the claim it was cited for was a reading of it (2026-10-23, W896's
   evidence). The model had no way to say "quoted" against "my reading of the quote".

## What each missing part would let a session check

- A typed **kind of grounds** (quoted, derived, measured, relayed, judged) lets a shape refuse a
  done-claim whose only grounds are a relayed statement, or a ruling that rests on a derived reading.
- An explicit **warrant** lets a session see why a step is licensed, and see when the licence is a
  standing rule (the SOP) and not a one-off.
- A **qualifier** lets "unverified" be asserted and later withdrawn, instead of rewritten in prose.
- A **rebuttal** relation lets a session find what defeats a claim, and a ruling that supersedes
  another, which today it finds only by reading the later text.

## What this document does not do

It does not say which standard types these parts (that is W910, W911). It does not test the map
against mtools' five demoted cards, which W909 does. And Toulmin is one model among several: Walton's
argumentation schemes and the Argument Interchange Format (AIF) carry the same parts with critical
questions attached, and are in W910's survey.
