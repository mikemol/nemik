# W228: nemik-check evaluates the realizability policy over every queue

Design note, 2026-10-08, written under the md0 HOLD (no build, test, commit or tree scan until the
host sends RELEASE). Nothing here is code. Cause: luthen-observability:W666 and :W665; the writer
side is mtools:W848 (mtools-25 holds its note). Operator: "W228 is the one to focus on."

## What the operator asked, as relayed

How Rego can enforce the realizability charter as a lifecycle for minting waypoints. The proposal
from the luthen host (github-28):

- Minting is never refused. Four gates govern ADVANCE: minted -> ready -> working -> done.
- Each gate is decided from queue fields plus timestamped observed facts.
- The verdict is `level=<deepest clean gate>` plus a residue ledger typed by gate and reference
  arm. A deferred gate is allowed (residue parked, reference noted); a waiver is a violation.
- mtools:W848 is the WRITE side (a transition is evaluated before it is written). W228 is the
  fleet-wide READ side: evaluate every waypoint of every queue as it stands, print its coordinate
  and its ledger.

## One policy, two inputs

The same Rego package answers two questions. The write side hands it a TRANSITION document
(`from`, `to`, the fields it would write); the read side hands it a STATE document (the waypoint as
it stands, asking "what is the deepest gate this state satisfies?"). One policy file, so the two
cannot disagree about what a gate means.

Output (both sides), AGREED 2026-10-08 with mtools-25 (mtools:W848; luthen's W666 to emit the same):
`{ref, level, reference_arm, residue: [{gate, reference_arm, what, closes_by}]}`.
`level` is the deepest gate that is fully clean: `none` (below constructible; token proposed, to be
confirmed), `constructible`, `reachable`, `observable` or `coverable`. `level=coverable` with an
empty residue IS runtime-valid. There is no `admitted: bool`: the charter forbids a bare bit. A
caller that needs a yes/no derives it (`level` at or above the gate the transition requires). A
per-residue `reference_arm` overrides the verdict-level one (an operator ask is judged against the
operator). (My first draft said `coordinate` and `closes_with`; both names are given up.)

Deferral (mtools): an optional writer-owned list `deferred:[{gate, reference_arm, what, closes_by}]`
on the waypoint. A deferred gate stays residue, so the level stops below it. There is no waiver
field, and the policy treats any key named `waive` or `waived` as a violation. A dropped waypoint
carries `drop.gate`, `reference_arm` and `reason`. nemik's adapter will carry both into the state
document once mtools:W849 defines the fields.

Policy file (mtools): package data at `mikemol/pathsforward/policy/realizability.rego`, read by
nemik from the vendored wheel. Runner: nemik and mtools use the same pinned opa and
`opa eval --format json --stdin-input`; a fleet batch is one eval with a list as `input.items`, so the
policy has a per-item rule and a set rule. CONFIRMED by mtools-25 (W850): package `data.realizability`,
per-item rule `data.realizability.verdict`, set rule `data.realizability.verdicts` (a list in
`input.items` order). Levels: none, constructible, reachable, observable, coverable. Pin: mtools'
`pytestspec/opa.py` has PINNED = "1.20.2", equal to nemik's v1.20.2 (the sha256 stays nemik's).
Sample queue records with `deferred` and `drop.*` are in mtools:W849's evidence, marked illustrative.

Rule for nemik's adapter: an absent field means NOT DECLARED, never clean. The state document must
carry `null` for a field the queue record lacks (not `false`, `""` or `[]`), so the policy can tell
"no next step" from "not stated".

## The gates, for a waypoint

Reference arm (default): the queue system, meaning the writer, nemik's graph and the observers.
Every residue is tagged with it (`@ queue`), so it stays portable. An operator ask is judged
against the operator as a second reference arm (`@ operator`), not against the queue.

| gate | common_mode (what exists) | residue (what is missing) | existing nemik shapes that already measure it |
|---|---|---|---|
| constructible | a title that names one step; well-formed lists and blockers; a `next_bounded_step` once the card is ready or working | no next step; a bundled title; a list stored as a string; a symbol with prose attached | BundledTitleShape, ListFieldShape, MalformedBlockerShape |
| reachable | every `enables`, `caused_by` and `blocked_on` resolves; a block on a peer is claimed; a block on the operator states its ask; no edge into a dropped or landed item | an unresolved or landed blocker; an unclaimed block; an umbrella cited instead of its child; an unstated operator ask | WaypointShape, CausedByResolvesShape, EdgeIntoDroppedShape, BlockedShape, UnclaimedBlockShape, UnresolvedBlockerShape, LandedBlockerShape, UmbrellaBlockShape, OperatorAskShape |
| observable | a done card has evidence someone who was not there can check; a witnessed card's witness evaluates (HELD, never passed, when a fact is unknown) | done with no evidence; a witness whose facts are unobserved | none today (new) |
| coverable | the case space is enumerated: an umbrella lists its children; the priority vector is scored | an umbrella with an unenumerated remainder; an unscored vector | none today (UNSCORED is counted, not a finding) |

So reachable is mostly a re-expression of shapes nemik already computes (the luthen host guessed
this). Constructible is half there. Observable and coverable are new.

## Where the judgment lives

The graph-shaped facts (does this blocker resolve, is this block claimed, how many open children)
stay in Python: nemik already derives them as `annotate()` marks and SHACL results. They are passed
to Rego as booleans and counts in the input document. Rego decides what they MEAN for each gate.
This keeps rdflib out of Rego, makes the policy a small pure function, and means a shape finding and
a residue line cannot drift apart: the residue is built FROM the shape result.

Unknown is not clean. A fact the reader could not observe is `null` in the input, and the policy
turns `null` into residue ("unobserved"), the way luthen's W666 HOLDs on unknown. Silence never
passes a gate.

## Runner

nemik already pins opa (MODULE.bazel `@opa`, also in the image test stage) and runs it for
`nemik-witnesses`. The read side makes ONE `opa eval` over a batch (`input.waypoints[]`) rather than
one per waypoint (there are ~2500 nodes fleet-wide). mtools' pytestspec/opa.py shells OPA too; both
should use the same invocation contract (stdin input, `--format json`, a pinned binary). No second
runner is invented.

## Where the policy file lives (open: mtools-25 decides)

Proposal: in the pathsforward package, as package data
(`mikemol/pathsforward/policy/realizability.rego`), because mtools owns the writer and the policy
must ship with it. nemik already vendors that wheel, so it reads the one file and carries no copy.
Until mtools ships it, nemik may carry a draft under `src/nemik/data/` and switch when it lands.

## Surface in nemik

- `nemik-check --realizability [--repo R] [--all] [--json]`. Default: per repo, a count by
  coordinate, then every waypoint that is not `runtime-valid` with its ledger lines (a fleet of
  hundreds of open cards would otherwise bury the signal); `--all` prints every waypoint.
- The existing shape warnings stay as they are (they page; the residue is the typed view of the same
  facts). `nemik-check` must not print a finding twice, so a residue line carries the shape name it
  came from.
- `nemik-metrics`: `nemik_realizability_waypoints{repo,coordinate}`, so luthen can alert on a repo
  whose cards sit below a level.
- Never in nemik-serve, the export or the static build in its first cut: the ledger quotes
  waypoint text (a `what` field), which the public view must not carry (withhold-whole contract).

## Stigmaturgy (operator requirement, relayed by github-28, 2026-10-08)

"This whole thing should support stigmaturgy": agents coordinate by deliberately leaving durable
marks in a shared medium that other sessions read and act on (stigmergy, made on purpose). The
vocabulary is the operator's; the standard terms (stigmergy, blackboard control, pull-based
attention) apply. nemik is the SALIENCE SERVICE a worker queries ("what deserves my attention
next?"), never a dispatcher. That is a constraint on the read side, not a new feature, and it
changes four things in the design above.

1. **Verdicts are marks, read, not private re-derivations.** A verdict computed privately by each
   session could differ between sessions (different clocks, different checkouts). So the read side
   prefers the PERSISTED mark: the per-transition ledger the writer leaves (mtools:W848/W851), and
   prints it with its provenance: `mark` (written at a transition, with its time and policy
   version) or `derived` (no mark exists: every card minted before the writer hook, evaluated now
   from the state document). Where a mark exists and the state has moved since, print both and say
   the mark is stale (the point of a mark is that others can see what the last agent saw).
   AGREED with mtools-25 (mtools:W849/W852): the marks live in `.claude/paths-forward.marks.jsonl`
   beside the queue, append-only, one JSON object per transition, apart from the text `.ledger`:
   `{as_of, op, symbol, policy_version, input_digest, verdict:{ref, level, reference_arm,
   residue:[{gate, reference_arm, what, closes_by, closes_ref?}]}}`. `policy_version` is the sha256
   of `realizability.rego`; `input_digest` the sha256 of the canonical input; `as_of` is the same
   `now` the policy received, so a mark can be re-derived from its record and a stale one is
   detectable (an `as_of` older than `max_age_seconds`, or a `policy_version` that is not the
   current policy's). Residue entries carry an optional `closes_ref` (`<repo>:W<n>`, validated like
   `caused_by`); nothing parses the prose, so nemik-rank reads `closes_ref` only. The marks file
   quotes waypoint text (`what`), so it stays out of nemik-serve, the export and the static build.
2. **Residue is an attractor.** A residue's `closes_by`, when it names a waypoint, raises that
   waypoint's salience in `nemik-rank`: a card that closes N residues at gate G outranks an
   equally weighted card that closes none, so the gap draws the next agent. This is a new rank
   objective (`closes`, beside operator, band and weight) under the same configurable composition
   (`rank-weights.toml [order]`), and it needs `closes_by` to be machine-resolvable (a
   `<repo>:W<n>`), not only prose: asked of mtools as a structured part of the residue entry.
3. **Marks decay.** A mark or observed fact older than the policy's `max_age_seconds` loses force:
   it floors the gate (the residue becomes "stale @ <age>"), never counts as a pass. The policy
   takes the time as an INPUT (`input.now`), so a verdict stays a pure function of its input (the
   charter's determinism invariant) and nemik prints the `as_of` it used; tests pin it.
4. **Hosts leave marks too.** `host-apply.json` (W233) is a mark the host root leaves: rows carry
   `as_of`, so decay applies to "row X applied", and a cutover step cites `host:<id>` instead of
   prose.

`nemik-wake` and its nudges push to a sleeping session. RULED by the operator (relayed by github-28,
2026-10-08): "nemik-wake wakes; a sleeping session has no autonomy, being woken gives it such."
Waking is not dispatch: a sleeping session cannot pull, so the wake is what makes the pull possible;
once awake it queries salience and chooses its own work. So the wake and the nudges stay, they
assign nothing, and the salience-not-authority line holds for everything after the wake. The read
side adds no new push. (The operator's outside assessment that named stigmaturgy is at
`~/github/assessment.txt`; its citations are unchecked, so nothing here relies on them.)

## Residue salience as effective conductance (W235; operator points at gcalculus's model)

Proposed by the luthen host (github-28, 2026-10-08) from gcalculus/EXPLAINED.md; the operator named
the gcalculus model as the right one. Checked against that document: conductance is the carrier;
parallel `OR(a,b)=a+b`, series `AND(a,b)=ab/(a+b)`; node elimination is the same operation as
minimising dissipated power; values stay exact fractions until evaluation. By hand: `AND(g,g)=g/2`,
`OR(a,a)=2a`.

Adopted as the DESIGN BASIS for the `closes` rank objective:

1. A card's salience is the effective conductance from the pull's sources to it, solved by node
   elimination (star-mesh), which also handles bridged graphs that AND/OR alone cannot.
2. The bound is structural, not a cap: a residue adds one edge, in series with the rest of its path
   it cannot exceed the weakest link, and each extra hop attenuates. (A card that closes MANY
   residues adds in parallel and legitimately rises: that is the attractor, not starvation.)
3. No laundering: OR is not idempotent, so the same residue cited twice doubles visibly. Edges are
   keyed by source (a residue is one edge, however often it is cited), so a duplicate is caught.
4. Keep the fibre: the verdict mark carries the decomposition (which paths, which edges), not only
   the rank, which is what stigmaturgy asks.
5. A blocked, dropped or landed edge is REMOVED (an open circuit), never weighted zero; conductances
   stay strictly positive.
6. Two decays, not one: HARD staleness (floor the gate) for SAFETY facts and verdict marks (W236);
   SMOOTH decay for SALIENCE marks, one half-life being exactly `AND(g,g)=g/2`.

NOT yet defined (each blocks code; W237 settles them):

- The SOURCES of the pull. WORKING ANSWER (github-28, 2026-10-08, a suggestion, not the operator's
  ruling): inject demand at the residue-bearing waypoints (each residue a current source, weighted by
  its gate) and ground a super-sink joined to the ready frontier (what a worker can pick up now). A
  ready card's salience is then the CURRENT through it to the sink, not a conductance. Why it fits:
  Kirchhoff conserves current, so total salience equals total declared demand and no card gains
  without another's demand flowing through it (no starvation as a law, not a cap); a card serving
  many residues carries their summed current; the per-edge current is the decomposition the mark
  keeps (which residues a pick serves); a residue with no path to the frontier carries zero current
  and is reported as STRANDED DEMAND, the reachable gate's failure made visible. One reduced
  Laplacian solve (sink grounded) gives every card's current at once. Reading: a card's salience is
  its SHARE of the total demand, which is conserved.
  Still to settle inside it: (i) SYMMETRY. A resistor network is undirected; dependencies are
  directional (a needs b). Undirected flow lets demand spread along an edge both ways; the
  alternative is a directed absorbing walk toward prerequisites, which is not the calculus gcalculus
  models. Which is right is a modelling question for W237 and gcalculus. (ii) The sink's wiring: the
  conductance joining each ready card to the sink (equal? by band?) shapes every share. (iii) Demand
  units: the weight per gate and the smooth decay of an aged residue's demand (half-life) are
  declared data.
- The EDGE WEIGHTS: which conductance an `enables` edge, a `closes_ref` edge and each gate carries.
  They are policy, so they belong in `rank-weights.toml` (declared data, a reviewed diff), not in
  code.
- How the objective joins the existing order: it is one more objective under the configurable
  composition (`[order]`: tiers, Pareto fronts, scalarization), not a replacement for the
  downstream weight.
- Cost and determinism: exact fractions with node elimination can fill in; the open graph is a few
  hundred nodes, to be MEASURED (after the md0 release) before choosing exact elimination over a
  deterministic sparse solve. Same input must give the same ranking (nemik:W119).
- Consumption: nemik should take gcalculus as a sha-pinned, vendored package (not its working
  tree), or implement elimination itself and cite gcalculus's laws and witnesses as the spec. Asked
  of gcalculus (letter, 2026-10-08).

## Audit, then REPLACE (operator ruling on W237 (c), relayed by github-28, 2026-10-08)

The model is not one more objective beside the existing ranking: it REPLACES it, after an audit.
Operator: "We should be able to audit the existing ranking against the gcalculus model, show that
they match the existing predictions, and then replace the existing ranking objectives with the
gcalculus model." Sequence (agreement is the witness; each disagreement is a residue to decide,
either a bug in the old ranking or a missing term in the model, never averaged away):

1. EXPRESS each existing objective as a statement about the current-flow model, or find where it
   cannot be (W239; first pass below, a PREDICTION for the audit to test).
2. COMPARE: run both over the real queues, record every disagreement with its reason (W240; after
   the md0 RELEASE).
3. SWITCH nemik-rank to the model only then, keeping the old ranking as the comparison arm until
   the switch (W241).

First-pass mapping (existing ranking: tiers `[operator]` then `[band, weight]`, Pareto fronts inside
the second tier, scalarized as band*100 + weight; `weight` is the sum over each card's TRANSITIVE
DOWNSTREAM CLOSURE, each waypoint counted once, by class: local 1, peer 2, peer-blocked 8):

| existing objective | statement in the current-flow model | prediction |
|---|---|---|
| downstream weight | inject demand at every waiting card (its class weight: 1, 2, 8) and ground the sink on the ready frontier; the current through a ready card is the demand of everything whose route to the frontier passes through it | EXACT where each waiter has ONE route to the frontier (chains and trees): the current through the card is the old weight. They DIFFER on a diamond: a card waiting on two ready blockers is counted fully for each by the old ranking, but its demand SPLITS between them in the model (conserved). Each such case is a decision: the old double count is a bug, or the model lacks a term. |
| priority band | the card's OWN demand: a band weight injected at the card itself, which exits through its own sink edge | the old scalarization (band*100 + weight) is linear in the two terms, and current is linear in demand, so the mixed score is own demand plus downstream shares: exact in form; the band weights are declared data |
| Pareto fronts | EMERGENT (operator, 2026-10-08: "The gcalculus model provides it emergently"). Keep each card's FIBRE, its current split by source class (each demand class: a band, a downstream class, an operator ask, a residue gate), instead of collapsing it to one number. Card A dominates card B when A carries at least B's current from EVERY class and more from one: a partial order, whose non-dominated sets ARE the Pareto fronts. The scalar (the collapse map, gcalculus's evaluation) is only the final step that breaks ties inside a front | My first pass said "no counterpart", which was wrong: it only looked absent because I collapsed the fibre. The old objectives (band, weight) become source classes, so the fronts fall out of the model rather than being imposed. The audit (W240) compares FRONT MEMBERSHIP as well as order; my earlier worked example (E before C despite C's higher scalar) is the old ranking agreeing with the fibre order, not a disagreement |
| operator asks first | RULED (operator, 2026-10-08, directly): "Kind of? You can use the model to say 'this is what I think needs to happen in order to do your ask / this is what that overrides' in order to use the operator's interaction to guide refactoring of the graph so that their asks live within the model and are responsive to it, rather than outside of it." | NOT a strict tier and not an infinite weight: an ask is DEMAND injected at the asked card, and the model answers the operator with two readings (below). The operator's reply refactors the graph (edges, splits, weights), so asks live inside the model. The strict tier (nemik:W111) stays only until the switch (W241) |
| tie-break to the lower symbol | none | stays as the final deterministic tie-break |

### Operator asks inside the model (W244)

An operator ask is a demand source at the asked card, and the model gives the operator two readings
before anything is reordered:

1. "This is what I think needs to happen to do your ask": the path its current takes to the ready
   frontier, edge by edge (the decomposition the mark keeps): the prerequisites that would carry it,
   in order.
2. "This is what that overrides": total salience is conserved, so the ask's demand takes share from
   other cards. The cards whose share falls (with versus without the ask) are what the ask displaces,
   each with how much.

The operator answers in the medium: if the path is wrong, the graph is wrong (a missing or false
edge, a card that should be split), and the fix is a queue edit, not an override; if the
displacement is unacceptable, the ask's weight is a declared number they change. The ask is then
responsive to the model rather than outside it. Conditions: reading 1 is only meaningful once the
model is DIRECTED (an undirected flow would name non-prerequisites as "what needs to happen", the
leak gcalculus:W208 showed); and the readings are shown, never acted on: nemik stays a salience
service.

Replaced objectives keep their configuration in declared data (`rank-weights.toml`): the class
weights become demand weights, the band weights stay, and the `[order]` composition is replaced by
the model's parameters (sink wiring, decay half-life).

## gcalculus's partial answer (gcalculus:W208, 2026-10-08): three findings that change the plan

Read from gcalculus's own queue (W208 claims nemik:W237; its full answer waits on the md0 cutover):

1. PACKAGING. There is no published package: gcalc is stdlib-only but its pyproject has no
   build-system. The solver has `r_eff`, `laplacian`, `eliminate` (star-mesh, exact), `freeze(keep=)`
   (Kron reduction to ports) and `glue_patches`/`Obstruction`, but the gluing is of POTENTIAL
   PATCHES, not port networks, and there is NO per-edge-current or grounded-sink API. So nemik
   cannot simply import "the model": the current-flow reading (a sink on the ready frontier, the
   current through each card) is not packaged. Either gcalculus adds it, or nemik implements it and
   cites gcalculus's laws and witnesses.
2. SYMMETRY IS A REAL DEFECT. Undirected flow leaks demand to non-prerequisites. Counterexample
   (gcalculus's leak.py, exact): a needs b; d needs a and e; b and e are ready; sink on {b, e}; 2/5 of
   a's demand exits through e, which a does not need. A directed variant is NOT claimed by gcalc. So
   the pure resistor model does not say "demand flows toward what must be done first". The audit
   (W240) will show this as disagreements; the replacement needs either a directed absorbing walk
   toward prerequisites (the same linear algebra, a different model) or an accepted leak. The
   "replace after audit" ruling stands, but "the gcalculus model as-is" cannot be the thing it
   replaces with: that is the first residue.
3. COST. A dense exact Fraction solve (degree about 3, sink on a tenth of the nodes): n=30 0.15 s,
   60 0.85 s, 120 7.5 s, 240 85 s, denominators up to 769 bits, about cubic. luthen's queue alone has
   hundreds of open nodes, so EXACT fractions are out without a sparse ordering. Determinism
   (nemik:W119) then has to come from a fixed elimination order in floating point (bit-for-bit for
   the same input and order), not from exactness. This weakens "the glued answer equals the whole
   one" from exact to numerically equal; the per-repo reduction (W242) still bounds the cubic cost
   by one repo's size.

Witnesses gcalculus names for the laws nemik tests against: operator/strata/non-idempotent,
network/idempotence/doubling, operator/carrier-laws/*,
operator/afforded/laundering-is-structurally-blocked.

## The model is DIRECTED (operator, 2026-10-08, directly)

"The model is already directed; that's what blocks vs enables is." So the leak in gcalculus:W208's
counterexample is an artefact of treating the links as symmetric: demand flows only from a card to
what it NEEDS (along `blocked_on`, the reverse of `enables`) and is absorbed at the ready frontier;
it can never reach a card the source does not need. Consequences:

- The symmetry question (W237) is closed; the leak is not a residue of the model.
- Cost: on an acyclic queue graph, demand propagates in ONE pass in dependency order (linear in
  nodes plus edges), so exact fractions become affordable again and the cubic dense solve is not
  needed. A cycle (queues have them; the web view already cuts back-edges) needs a small linear
  solve inside its strongly connected component only.
- The fibre (demand per source class) propagates as a vector, linearly, so the emergent Pareto
  fronts cost the same pass.
- Reading 1 for an operator ask ("what needs to happen") is exactly the directed path its demand
  takes.

Open question this exposes (for the operator): `blocked_on: [a, e]` means D needs a AND e (both
required, not alternatives). Does D's demand go IN FULL to each prerequisite (each is equally
necessary; this is what the old downstream weight does, but then total salience exceeds total
demand and the conservation property is lost), or is it SPLIT between them (conserved, but each
prerequisite looks half as important)? In gcalculus's terms, `OR` (parallel) composes ALTERNATIVES;
conjunctive prerequisites are not alternatives, so neither generator obviously fits. This is the
diamond case of the audit, and it decides it.

### Direction as a differential pair (operator: "look at what gcalculus does for differential channels; a +evidence and -evidence")

Source read: gcalculus's letter `inbox/2026-08-21-gcalculus-your-paraconsistency-is-filed.md` (Q2,
"the differential pair"): a quantity is carried as a PAIR, positive and negative evidence. Its class
(the ratio) is lossy, `(3,5)` and `(6,10)` being one class (`operator/mass/class-is-lossy`; the fibre
is a torsor), and the RETAINED pair is what tells ignorance (both channels weak) from conflict (both
strong). Contradiction is carried as a quantity, never as a truth value, so nothing explodes.

My reading for nemik (for the operator to confirm; not yet ruled):

1. Each dependency is witnessed on TWO channels: `+` evidence from the prerequisite's side (A
   `enables` B) and `-` evidence from the dependent's side (B `blocked_on` A). The DIRECTION of the
   edge is the differential of the two: the common mode is rejected and the oriented residue says
   who needs whom. That is why the model "is already directed".
2. gcalculus:W208's leak came from collapsing the pair into ONE symmetric conductance: taking the
   class and dropping the pair. Keep the pair and the edge cannot carry demand backwards.
3. The retained pair is a reading in itself: both channels agree (the edge is declared from both
   ends); IGNORANCE (one side only: B waits on A but A names nothing, which is nemik's
   UnclaimedBlockShape; or A enables B but B is not blocked, which is ready, not blocked); CONFLICT
   (the two sides say different things: a blocker that has landed while the waiter still cites it,
   LandedBlockerShape; an edge into a dropped card, EdgeIntoDroppedShape). Today those are boolean
   warnings; in the model they are quantities on the pair, kept rather than quotiented.
4. gcalculus's near-collision finding (`math/nearcollision/...`: two different topologies agree to
   four decimal places) argues for EXACT arithmetic wherever it is affordable, which the directed
   one-pass propagation now makes it.

The conjunctive question, RULED (operator, 2026-10-08): SPLIT, conserved. "This is the way. Let the
physics do the work." And: "the nodal solve answers this question as the solve frontier advances.
You only get confused because you try to solve in advance of the frontier." So there is no rule to
fix in advance (not "half each"): node elimination, ordered from the ready frontier inward, decides
how a node's demand divides among its prerequisites at the moment that node is eliminated, from what
has already been reduced behind it. As cards land, the graph changes and the next solve re-divides
(when A lands, B's need flows wholly to C). The diamond disagreements in the audit (old double count
vs conserved split) are therefore decided for the model.

Correction to "The model is DIRECTED" above: "one pass in dependency order" holds only where the
structure is a tree or series-parallel. Where prerequisites reconverge, the split is the nodal solve
(elimination from the frontier, star-mesh), which is what the operator means; its cost is bounded per
repo (W242) and per cycle component.

## Cost and determinism: reduce each repo to its ports, glue (operator on W237 (d); W242)

Operator: "conveniently, because of network theory et al, these measurements can be applied to
smaller graphs and glued together for the larger solve." The luthen host's reading, with the
conditions I found (the mathematics is standard: eliminating a subnetwork's interior nodes, the Schur
complement or Kron reduction, gives an exactly equivalent network on its ports):

1. Each repo's queue is a subnetwork; its contact with the rest is the cross-repo edges (ports).
   Reduced to its ports it carries a port matrix AND the equivalent injected currents (the demands
   inside it), both exact. The fleet solve is then a small solve over the glued port networks.
2. Per-card salience needs the card's current, which is interior. After the port solve, each repo
   back-substitutes locally (cheap: one repo's size). So the cost is each repo's interior
   elimination plus the port count, not the fleet.
3. Conditions the glue must respect:
   - The global sink touches every repo (each repo's ready cards join it), so the sink is a port of
     every subnetwork.
   - Cross-repo edges belong to the GLUE layer, not to a reduction: their conductance depends on the
     neighbour's card (the class weight is peer vs peer-blocked), so a reduction depends only on its
     OWN queue and can be cached by that queue's digest. A change in another repo cannot stale it.
   - Exactness is exact arithmetic. In floating point the glued and whole-graph answers agree only
     up to rounding, so use exact fractions (per-repo sizes are small) or a fixed elimination order,
     to keep nemik:W119 (same input, same order) bit for bit.
4. Cited by the luthen host: gcalculus states "any split of the work gives the same answer", proved
   in its Agda file. I have NOT read that file; it is cited, not re-proved, once I have found it
   (asked of gcalculus). The gluing obstruction (which overlap fails, an H1 class) maps onto a finding
   nemik already reports: in a partition the only shared things are cross-repo edges described from
   both sides (A enables it, B waits on it), and a mismatch there is an unclaimed or unresolved
   block.
5. Stigmaturgy: a reduced port network stamped with the digest of the queue it came from is a
   DERIVED mark in the same sense as W234's (provenance `derived`, stale when the digest differs);
   whether to persist it as a cache file or recompute it each run is decided at W242, by measurement.

## Host apply as a mark (W233, luthen-observability:W665)

The host-apply DAG is luthen's to EXPORT, nemik's to READ. luthen's vocabulary (2026-10-08): 45
activate kinds in `checks/host_activate.py` KINDS, each a fixed ordered tuple of argvs run as root
after the kind's files land, grouped by effect: install only (no process touched), reload in place,
RESTART a running service, enable a timer and queue a first run, start long or heavy work now
(drain-tier, drain-copy, bees-drain, drain-image: an apply that touches those rows starts a tier
pass), enable for next boot only, package installs, tmpfiles only, other.

Shape (luthen's two notes taken, plus two asks of mine). `host-apply.json` v1, beside liveness.json
and withheld.json:

    {version:1, as_of,
     kinds:{<kind>:{effect, restarts:[{unit, verb}]}},          # verb: restart|try-restart|start|enable-now|reload
     rows:[{id, activate:<kind>, after:[row ids], applied:{at, digest}|null}]}

- A row points at its kind, so the ordering and the restarts are stated once (per kind, not per row).
  `restarts` is structured, never prose.
- Ask of luthen: leave the `argvs` OUT of the export. nemik never executes them, they are root
  commands, and the effect class plus the structured restarts say what a planner needs. Add an
  `effect` per kind (the grouping above), because "start heavy work now" is exactly what a hold or
  a cutover gate must be able to refuse.
- Graph on nemik's side: Row -[activate]-> Kind -[restarts]-> Unit(verb). "What replacing
  var-lib-rancher.mount restarts" is then a walk: row, kind, units.
- Citation: `host:<id>` in a waypoint's blocked_on or evidence, resolved by form plus the export (as
  the `cal:` refs are). A row that does not exist yet (home.mount and srv-media.mount before
  luthen-observability:W663 adopts them) is an unresolved citation, never a pass.
- Witness: "row X applied" is a fact over a new closed observer, `input.apply["<id>"] = {applied,
  at, digest, as_of}`, read-only, no code executed. It is a mark with an `as_of`, so decay applies:
  an export older than its policy's `max_age_seconds` floors the gate (stale), never passes.
- Privacy: not served in the first cut (host paths and digests stay off the public view).
- Debt: luthen builds the export from host_activate.py, a debt file; a clean extracted kinds table
  may have to come first (luthen's call).

## Open questions (each blocks code, none blocks this note)

1. Field names of the shared verdict: AGREED (see above). Still open for stigmaturgy: a structured
   `closes_by` (a ref) beside its text, and the per-transition ledger's location and line format
   (so nemik can read a mark): both asked of mtools (W849/W851).
2. Which lifecycle stage requires which gate? Proposal: ready needs constructible, working needs
   reachable, done needs observable and coverable. The read side reports the coordinate either way.
3. How is a DEFERRED gate recorded on a waypoint (the charter allows deferral, forbids waiver)? It
   needs a field the writer owns (mtools:W848).
4. Does observable need a fact observer for "evidence is checkable", or is a non-empty evidence with
   a commit, path or command enough for the first cut? (A first cut can only check shape, not truth.)
5. Is `coverable` defined for ordinary leaf cards, or only for umbrellas and scored vectors?

## Not decided here, on purpose

The remediation of a residue is the proposer's act, not the policy's (charter, Boundary): the ledger
names what would close it (`closes_with`) and nothing more.
