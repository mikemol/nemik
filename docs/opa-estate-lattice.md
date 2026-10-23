# Estate's witness lattice and nemik's use of OPA: do they fit? (nemik:W912)

The operator asked (2026-10-23) that the interlocking, lattice pattern estate is working on be
congruent with, reinforce and complement nemik's alignment with OPA. This reads both from their
sources and says where they fit, where they would join, and where they differ. Marked **(code)** when
I read it in the source, **(estate)** when it is estate's own statement in `docs/enclave.md`, and
**(mine)** when it is my reading.

What each side is. The pattern is the operator's own definition (estate session d9d766b9 line 5790,
origin human, read myself): "the interlocking pattern that luthen-observability uses to ensure that
before a change is made, the state is what it is expected to be, then the change made is shown to
have actually been made, and to have become the state. Think 'witness lattice over states and
transitions'". Estate's version (estate): states are nodes, a transition is an allowed edge, a
`before` witness (STAR-S) must find the expected prior state, the same artifact is applied, an
`after` witness (STAR-R) must read the declared target back through a path independent of the write,
must differ from the pre-act reading (`advances`) and be read after the act began (`fresh_since`);
the ledger entry's hashes chain one transition's after-state into the next one's expected prior
state; an unevaluable witness is never green. Interlocks are a gate before the pipeline:
`defer(kind, facts)` asks the pinned opa for `data.<pkg>.interlocks.<kind>.defer`, a set of messages,
one per unmet precondition (mtools `waldo/planinterlock.py`) **(code)**. Nemik's OPA use is
`wcag.rego` (facts measured by `wcagfacts`, "the facts are measurements and this is the judgement",
no waiver), the realizability policy under `--certify`, and Rego witnesses: observers gather exactly
the facts a query names and `opa eval` decides true, false or undefined (`witnesses.py`) **(code)**.

## Congruent: the same three rules

1. **Facts are measured, the judgement is Rego.** `wcag.rego` takes luminances nemik measured;
   `witnesses.facts` takes only what the query references from a fixed set of observers; `defer`
   takes facts the consumer passes. No policy reads the world itself. **(code)**
2. **Cannot evaluate is not met.** Nemik: an unobservable fact makes a witness `undefined`, and
   `opa_json` returns None when opa is missing or exits non-zero, which `evaluate` turns into
   `undefined`; an undefined witness is never counted as done. Mtools: `defer` returns None when opa
   is not the pinned version or evaluation errors, and the caller treats it as deferred. Estate:
   "unobservable is not passed", `witness-unevaluated`. **(code, estate)**
3. **A pinned opa.** Nemik resolves one pinned opa shared with pathsforward (`NEMIK_OPA`); the waldo
   takes `config.opa_pin`. Whether the two pins name the same version is not checked here. **(code)**

## Complementary: what each has that the other lacks

| Estate's lattice has | Nemik has |
|---|---|
| a **state** claim per object, with a before and an after reading | a **card** claim ("done") with a lifecycle and a free-text evidence |
| `advances` and `fresh_since`: the after-reading must differ from the before and post-date the act | `input.now` and observer values, with no before-reading to compare to |
| a hash chain: after-state of one transition is the expected prior state of the next | no chain; a witness stands alone |
| `defer` returns a **set of messages**, one per unmet precondition | a witness returns one verdict plus the facts that decided it |
| "a witness must be able to fail": a witness that passes an empty or pre-act reading is a contract error | no such check that I found in `witnesses.py` |
| a place to say what must hold before an irreversible act (point-of-no-return) | a place to say what closes a card, and the cards that wait on it |

## How they would join (mine)

1. **Estate's after-witness is the grounds for a nemik card.** A card "the DNS apply landed" could
   carry a Rego witness over the verdict the waldo already prints (one JSON line, fixed state
   vocabulary), so the card closes from the read-back, not from prose. That needs one new observer
   in nemik's closed set (a verdict read from a published copy: estate seals the originals in the
   principal's state dir, which the agent session cannot rely on reading, and estate itself notes
   the agent and operator are the same Unix user). Estate's own witness commands and baseline record
   are not written yet **(estate)**, so this is a design to agree, not an interface to code against.
2. **`defer`'s shape is a better witness result.** A set of unmet-precondition messages is what
   `docs/toulmin-map.md` calls the rebuttal and qualifier a card lacks: a witness that returns which
   conditions fail, not only false, would let a card carry them.
3. **Nemik should adopt estate's "must be able to fail" and freshness.** A witness that is already
   true when the card is minted can close it on the first `--apply`, with no before-reading to show
   the card's own work changed anything. A baseline verdict at `--add` (a witness true at mint is a
   defect) and an optional `fresh_since` would give nemik estate's discipline for cards.

## Where they differ, and are not in conflict

- Estate's witnesses are judged today by the contract's `json_empty` and `must_contain` operators,
  not by Rego, so only half of its lattice (the interlock half) runs on OPA **(estate)**. Moving the
  `after` judgement to Rego would make the two use one engine; that is estate's call.
- The granularity differs on purpose: estate's lattice is over the states of managed objects and
  their transitions, nemik's over claims about work. They meet at the card that says an apply landed.
- Neither side has written the join, and nobody owns it: estate's interlocks and witness commands are
  unwritten, and nemik has no observer for a verdict.

## What follows

Two cards, W913 (nemik witnesses must be able to fail at mint, and may carry a freshness bound) and
W914 (an observer for a published waldo verdict, after estate states its witness JSON), and a
question to estate-dd about whether the `after` judgement will be Rego.
