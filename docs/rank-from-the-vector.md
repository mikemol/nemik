# Ranking as one circuit

nemik:W2325. **Design only: no code, no change to any repo's round.** It touches every repo's
round, so the cold review applies before any build. The review path ends at the warm and cold
reviews, per github-00's relay of the 2026-11-17 ruling (not read by me); the operator is
informed, and is engaged on this one.

This is the durable home of the design. The operator's worry (relayed by github-00) is that the
understanding behind it dies at the next compaction, so the derivations and their exact checks are
written INTO this document (the appendix is a script that runs and asserts), not left as references
to a conversation. Each citation is marked **verified** (read in the source or the committed object,
with the sha) or **relayed** (from a peer, not checked by me).

Versions: v1 to v5 ranked by Pareto fronts with the circuit ordering inside a front, and failed
(the front contradiction). v6 removed the Pareto layer. v7 folded in the cold review of v6 and the
operator's rulings since: every card has a cost; De Morgan; the rails are independent
(paraconsistent); a Wheatstone bridge translates between the two readings of them; velocity is gain,
"logsumexp partially applied". **v8** folds in the cold review of v7, whose defects were in the
design, not the arithmetic: cost scored FOR a card (the sign is now against: cost is a gain on the
demand); mass was read from an arm current, then from a bridge supply; BOTH on a ready card means
wanted and expensive; the independence witness compared the wrong cards; the soft-maximum exponent p
was not derivable and is now marked open; the velocity witness moved a quantity that is not ranked.
**v9** folds in the cold review of v8, whose defects were in the ranking value and the mass readout:
v8 called the value the ODDS of the pair, a form el-atlas forbids inside the logic (Law 3.1, Lemma
3.2, Law 4.2, CX-1, P-1) and the cold review showed it carried a hidden weight, the exponent on
cost. The value became a gain stage that holds the cost; v9 called the exponent "forced". Mass is
the product by definition (el-atlas line 177), not a bridge readout. The median stand-in for a
cost-less card is withdrawn: it moved with unrelated arrivals.
**v10** folds in the cold review of v9 with mechanical fixes only, no new design. Its central
finding stands and is now said plainly: **the order is `pro / cost`, a ratio**, order-identical
to v8's odds on 200 costed cards, `u0` times `E+/E-`, the bias shadow in el-atlas Remark 3.5's own
list. It is admissible only as a named, external decision step (Law 3.1 line 235, CX-1 lines 1234
to 1235, Remark 3.5), and it is the doc's CHOICE, not a derivation: v9's "forced exponent" was
degree -1 homogeneity restated, and is withdrawn. The choice is the operator's to confirm.
**v11** writes in the HOST ruling of 2026-11-22 on v10's six open questions (github:W146; warm review
github:R247, cold review github:R248; section "The host ruling" below). The operator returned the six
questions as review questions, so these are host rulings that stand until the operator or the replay
(nemik:W2393) says otherwise: Q1 the value is the delivery cost SAVED, weighted by demand (output is out;
several accelerators on one card compose multiplicatively); Q2 velocity-first stays unconditional, the
conditional rule a replay candidate; Q3 a cost-less card leaves the value ranking for grooming (nemik:W2360
cost estimates, W2392 the shape); Q4 no floor, only a larger demand source; Q5 k = 1 and the objective are
NAMED EXTERNAL choices; Q6 both routes to decomposition, by the absolute rules, no median cut. The appendix
gains the v11 checks and still runs as one script. Where I am not sure, a bullet says OPEN rather than
asserting.

## The rulings this rests on (each verified in a host or gcalculus transcript, origin human)

Host transcript 695f3e0a:
- 188832: "the vector is more meaningful than the band bullshit. The bands are a flat ranking of a
  hyperdimensional weighting problem."
- 188919: "I'll give you a hint: what's the velocity of a broken gate?"
- 188939: "don't make it linear. And *pay attention to salience and the gcalculus/conductance/
  logsumexp math that exists precisely to help with this entire class of problems!*"
- 188975: "velocity is the conductor everything else must pass through ... every 'blocked on' is a
  coefficient for what passes through that edge. That's what salience is supposed to be; 'blocked
  on' is resistance. 'Enables' is conductance."
- 189088: "This is why the circuit model *works*. I've woken substrate and g-calculus ..."
- 189510: "I can't imagine any card lacks a cost. If it does, it hasn't been groomed or decomposed..."
- 189533: "de morgan answers this one; series is NOT(parallel), and series is NOT(NOT(series)) and
  parallel is NOT(NOT(parallel)). And AND is NOT(OR), OR is NOT(AND), AND is NOT(NOT(AND)), OR is
  NOT(NOT(OR))."
- 189553: on the el-atlas rails being independent: "yes. This is why it's paraconsistent logic."
- 189606: "there are two ways to read them: One is as a differential pair, where *ideal* is for them
  to be in balance, and an imbalance carries the meaning. The other is as independent accumulators.
  *How* you interpret them depends on the model, but a wheatstone bridge can be used to translate
  between the two interpretations."
- 189636: "the word you're looking for here is `gain`."
- 189692: "This is also logsumexp partially-applied. Gain happens when you exponentiated to change the
  domain."
- 100702 (2026-10-26): "we wanted velocity improvements to come before the things we want velocity
  to carry." The W993 paydown lift cites 92679 and 93406.

gcalculus transcript cffb638b: 53180 "the nodal solve *is* the cone expansion. It's just a question
of where you begin your frontier." 52311 "g-calculus is not idempotent, and it is
resource-sensitive."

## The host ruling of 2026-11-22 (github:W146), and the objective it names

**Warrant, read from the inbox letter `inbox/2026-11-22-github-00-w2325-six-questions-host-ruling.md`
(relayed by github-00, not re-read by me in the host transcript).** The operator returned the six
open questions of v10 as review questions: host session 695f3e0a, 2026-11-22, typed "Hell if I know
the answers to any of these questions. This is warm/cold review stuff." The standing rule (change-review
step 9; host L161970, L180913) is that a choice between designs is not an operator ask: it gets a warm
and a cold review, and the host rules on their verdict. The warm review is github:R247, the cold review
github:R248 (both in the host queue). This is a **HOST ruling, not an operator ruling**, and it stands
until the operator or the replay (nemik:W2393) says otherwise.

**The objective: a named host choice, not an operator warrant.** The rulings below use one objective:
minimize the integral of outstanding demand over time, the sum over cards of demand times completion
time. The warm review drew it from L191695 ("an integral over cards over time") and L100702 ("backlog
burning down"). The cold review found that reading **UNWARRANTED, though not refuted**: the words support
an integral shape for a GAIN, not demand as the weight of the whole ranking, and L188939 ("don't make it
linear") allows a linear rule only as a named external decoder. So the objective enters this design as
a **NAMED EXTERNAL DECODER, the host's choice**, in the way v10 already cites el-atlas Law 3.1; the
replay (nemik:W2393) is what keeps it or changes it.

**Q5, the exponent: k = 1 (demand per unit cost) is accepted as a NAMED EXTERNAL CHOICE**, not as a
consequence of an operator warrant. The arithmetic holds: on v10's pair, (4, 2) against (3/2, 1), the
k = 1 order totals 12.5 and the k = 2 order totals 13.5 (checked in the appendix). It is Smith's rule,
optimal only for independent cards on one machine; with precedence edges and juggled work it is a
heuristic, and the replay measures the gap.

**One place where v11 generalizes the ruling rather than copying it (Q2).** The host ruling states the
exchange condition as "X first exactly when `c_X < (1 - 1/G) c_y`". Derived from the objective, that is
the case of a PURE accelerator, one with no demand of its own (`w_X = 0`); the exact condition is
`c_X < (1 - 1/G) c_y + (w_X / w_y) c_y`, of which the ruling's form is the pure case (asserted in the
appendix). The two are not in conflict, and the OUTCOME is unchanged: velocity-first stays unconditional,
and the conditional rule stays a replay candidate, to be tested in its general form.

The other four rulings (Q1, Q2, Q3 with Q6, Q4) are stated where they change the sections below.

## What nemik already has (read in src/nemik/, 2026-11-18)

- `weight = "flow"` (W241) IS the circuit. `nemik.flow` (gcalculus:W208, `scripts/flow_reference.py`,
  b9196cf): for each demand source a nodal solve on THAT SOURCE'S OWN prerequisite closure (its
  cone: direction is the queue's, W238), exact `Fraction`s, demand conserved and checked; the
  salience of a card is the current it absorbs, summed over sources (superposition of the reasons).
- Facts, each verified in code: `enables` and `blocked_on` are ONE edge kind (`index.successors`;
  conductance 1 by default, a per-edge override exists); **the ground is the cards that are ready
  or working AND have no open prerequisite** (`salience._open_graph` finds the prerequisite-free
  cards, `salience.salience_of` keeps the workable ones, W252); a prerequisite leaves the network
  when it is DONE, not when it lands (`open_card` is "has a state and is not Done"); `nemik.flow`
  returns the salience, the fibre per source, the potential at each source and the current per
  dependency summed over sources, not the potential drop across an edge; **wait-age is NOT in the
  ranking** (`AuditOptions.wait_weight` defaults to zero and only `nemik-rank --flow` passes it,
  `rank.py` 951 to 959; v6 said it was a source, which was wrong); the operator ask is a source of
  class weight 15 (W249), the other classes 1, 2 and 8, all declared data in `rank-weights.toml`.
- **The defect is the layer beside the circuit**: `[order] tiers = [["gate"], ["band", "weight"]]`
  and `[order.scalarize] band = 100`, the owner's `velocity` and `gate-repair` tags, the gate chain
  (`rank.py`, `score.py tagged_band`), and the critical floor, whose `rank.inversion` compares BAND
  NAMES, which include the tag bands (a velocity-tagged card counts as above the floor).

## The algebra (verified at gcalculus 1283876 unless marked)

`gcalc/kernel.py`: `NOT(x) = 1/x` (conductance <-> resistance), `OR(a,b) = a + b` (parallel:
conductances add), `AND(a,b) = ab/(a+b)` (series: resistances add; half the harmonic mean, a smooth
min that never reaches min); the other operators are generated from these; De Morgan follows from
NOT being an involution; "exact Fractions; no floats anywhere in the calculus". The carrier is the
positive rationals: no zero, no infinity, the poles unreachable (`machine.py` 664 to 665, key
`network/poles/unreachable`), so a contradiction degrades a quantity instead of exploding. AND and
OR are Kubo-Ando CONNECTIONS, not means (`priorart.py` 68 to 73). At b9196cf (`machine.py` 526 to
533): "the conductance solve IS the physics, min is its shadow" and "log-sum-exp is the physics, max
is its shadow" are ONE statement; `G_AND(a,a) = a/2` where `min(a,a) = a`; the tropical limit
discards the mass axis.

**What De Morgan does and does not say** (derived and checked in the appendix; this is the point
the v6 questions turned on). `AND(a,b) = NOT(OR(NOT a, NOT b))` relates the OPERATORS of the two
charts: series in the conductance chart is a sum in the resistance chart, and the same physical
connection read in the other chart is the same connection (a parallel connection of two
conductances is a parallel connection of their resistances, not a series one). So the CHART
(conductance or resistance) never changes an answer. It does not turn a parallel TOPOLOGY into a
series one, and it does not compute one rail's value as 1/x of the other's. That is the
operator's own reading (189606, 189553): the rails are independent accumulators.

**The geometric mean is forced, not chosen.** A Kubo-Ando mean has the form `m(a,b) = a f(b/a)`,
positively homogeneous (no reference scale). Symmetry gives `f(x) = x f(1/x)`; self-duality
`m(a,b) = 1/m(1/a,1/b)` gives `f(1/x) = 1/f(x)`. Together `f(x)^2 = x`, so `f = sqrt`: the geometric
mean. Self-duality alone does not pick it (non-homogeneous self-dual means exist, such as a
quasi-arithmetic mean through `x - 1/x`); homogeneity, symmetry and self-duality together do.
This is a fact about means of two quantities in ONE chart and ONE unit. v7 used it to call the
geometric mean the mass of pro and con, which the cold review rightly refused: pro (demand) and con
(cost) are in different charts and units, and the root leaves the rational carrier (the appendix's
`geo` works only on perfect squares, and is used there only to check this algebra). The design does
not need it for mass: the mass is the product, by definition (el-atlas line 177), and the
geometric mean survives only as the square-root shadow of that product, never evaluated in the
ranking.

## Two independent rails (paraconsistent), each in its own chart

Every card has a cost (operator, 189510), and the operator's own framing of the question it answered
was "what counts AGAINST a ready card": **cost counts against.** A card with none "hasn't been
groomed or decomposed": that is the operator's, and it routes the card to grooming or decomposition;
nemik-check already warns on a ready card with no manifest (per repo, above the declared
`[manifest_ratchet]` count, not per card), and the writer has `--size` and `--manifest`.

**v11, host ruling github:W146 Q3: the cost-less card is EXCLUDED from the value ranking and ROUTED TO
GROOMING** (189510: "If it does, it hasn't been groomed or decomposed"). The route must catch a card with
NO COST ESTIMATE, not only one with no manifest (github:R248): nemik:W2360 (every card carries a cost
estimate, derived by a reference class from measured landings, or the card's own) is the prerequisite,
and nemik:W2392 adds a nemik-check shape that warns on a ready card with no estimate, so the route is
enforced, not assumed. **Precedence (github-00, 2026-11-22): the session's own estimate wins over the
derived one, and both are scored by the same error series; a card with neither is the cost-less card.**
This ends v9's and v10's stand-ins: v8's median-cost stand-in "changes no order" was false (with costs
4, none, 1 and 2 against salience 3/2, 1, 1/2 and 1/4 the cost-less card overtakes the first, and an
unrelated arrival that moves the median reorders it again), and the identity cost `u0` that replaced it
moves a cost-less card against a costed one at each re-calibration; a card that is not ranked cannot
move. The cost's numeric scale is not typed: it is derived from landing history (open, below); what the
ranking needs is that costs are positive rationals.

- **PRO, demand, the conductance chart, composing in PARALLEL over prerequisites.** This is
  `nemik.flow` unchanged: the conjunctive split of the 2026-10-08 ruling (relayed: W228-
  realizability-read-side.md 349 to 356, "SPLIT, conserved"), the ready or working prerequisite-free
  cards at ground. Because it is unchanged, the regression holds exactly: with every g = 1 and no
  gain, the new solver reproduces today's salience for every card of every repo.
- **CON, cost, the resistance chart, composing in SERIES.** A card's con is its own cost plus the
  costs of its open prerequisites, each counted once (a set sum over its closure, so a shared
  ancestor is not counted per branch, the idempotent error). Finishing a card removes its cost from
  every closure that holds it: the series chart only ever FALLS.
- **They are independent**, so a card can be wanted and costly at once. Pro is a property of the
  cards where demand LANDS, the ready cards (the absorbed current); a waiting card holds demand as a
  source but absorbs none. The appendix gives exact pairs of READY cards, with the costs in a dict
  rather than as literals: P is the sole prerequisite of one source and absorbs 1; Q is one of two
  prerequisites of another and absorbs 1/2; both cost 2. Same con, different pro. And Q against R
  (cost 4, absorbing 1/2): same pro, different con. The rails are not 1/x of each other, so nemik
  does NOT sit on the inverse-locked locus (substrate's Lemma 2.6, el-atlas-spec line 204: the lock
  holds only on the embedded locus, line 1257), and needs the independent form. (v7's pair compared
  two WAITING cards, whose absorbed current is 0, and asserted a con equality that was a
  tautology; this pair does neither.) The operator's label "paraconsistent" (189553) attaches to
  el-atlas's two-rail logic; the cold review reports that gcalculus's scalar carrier does not claim
  it (`priorart.py`, explosion untyped; relayed, not read by me).
- **"D can rise" is a property of the pro rail's parallel structure, and only there.** In the flow
  chart, finishing one of two parallel prerequisites removes a path: the potential at the card
  rises (1/2 to 1 in the appendix). In the con rail adding or finishing cost in series is monotone:
  3 falls to 2. The first reading of the delay as elapsed time confused the two.

**The marginal of doing a card, per rail.** CON (series, exact and linear): doing card c removes
`cost_c` from every closure that holds it, so the weighted work removed is `cost_c x W_c`, where
`W_c` is the total demand whose closure contains c. A velocity card that cuts the cost of card x by
delta removes `delta x W_x`. No Sherman-Morrison formula is needed on this rail. PRO (flow): the
discrete changes of the nodal solve, PER CONE (below). A ready card is ground in the pro rail, so
"doing" it there is not a conductance change; it is read in the con rail. (This resolves v6's open
question and the cold review's "finish a ready card is ill-defined" without making ready cards
non-ground, which would break the regression: the cold review confirms that grounding ready cards
through their cost turns today's 2/3 and 1/3 split into 3/5 and 2/5 at unit cost.)

**This marginal is NOT a ranking term, and v7's use of it had the wrong sign.** `cost_c x W_c`
GROWS with the cost, so scoring it as a reason scored cost FOR a card (two cards of equal demand at
costs 1 and 10 scored 1/11 and 10/11, the dearer card first; v7's own queue, which also held the
sources' costs, gave 1/13 and 10/13). The work removed per unit of cost is `cost_c W_c / cost_c =
W_c`, the demand whose closure holds c. **That is NOT what the flow carries**: W_c is the UNSPLIT
demand, the idempotent downstream weight that salience replaced, and the flow carries the SPLIT,
conserved current each ground card absorbs (v8 said the flow already carries it; the cold review
refuted that). On the appendix DAG E has W_E = 3 against an absorbed 2, and F has W_F = 8 against 6
(asserted). So dropping the work-removed reason is a CHOICE, made because the W228 ruling is the
conjunctive split and `nemik.flow` is the one demand law (a second, unsplit demand would
double-count what the split conserves); W_c per unit cost stays a candidate reason the replay can
test. The con rail enters the ranking once, as the divisor of the value (below), where it counts
against.

**Which D, and the discrete formulas.** nemik.flow solves each source on its own cone, so D is the
sum over sources of per-cone delays, NOT one global solve. On the appendix DAG they differ (56 per
cone against 173/3 global: a global solve lets A's demand leak through B's branches), so every
pro-rail marginal below is per cone, summed over the cones that hold the card or edge.
- A node joining ground: `D - D' = phi_c^2 / M_cc`, exact (checked per cone).
- One edge's conductance up by delta: `D - D' = delta d_e^2 / (1 + delta Reff_e)`, with `d_e` the
  potential drop across the edge and `Reff_e` the effective resistance between its ends (not
  1/g), exact; shorting is the limit `d_e^2 / Reff_e`.
- **The derivative `delta d_e^2` is not the discrete change and it misranks.** Witness (exact):
  edge 1 in a bare chain carrying demand 3, edge 2 the same conductance but with a parallel two-hop
  path (effective resistance 1/6, not 1) carrying demand 17. At a relative speed-up of 10 (the
  conductance multiplied by 11, so G = 11 in the gain section's terms) the derivative gives 90
  against 1445/18 (about 80.3), so it ranks edge 1 first; the exact change is 90/11 (about 8.2)
  against 1445/48 (about 30.1), so it ranks edge 2 first. v3 and v5 used the derivative; it is
  withdrawn.

## Velocity is gain: solve first, then amplify

The operator's word is `gain` (189636), and it is "logsumexp partially applied" (189692): in log
space a gain is an additive shift `u -> u + log G`; exponentiating to the gain space turns it into
the multiplication `G x`; the sum of the amplified flows is `sum_i exp(u_i + log G_i) = sum_i
G_i x_i`, the parallel (OR) sum in that space, stopped before the final log. With rational `G_i` and
`x_i` it is exact in `Fraction`s: no `exp` or `log` is ever evaluated (the same move as the
exactness of the soft maximum below).

- **Where the active element sits.** The passive Kirchhoff solve conserves demand and runs FIRST, on
  the unaccelerated network (checked: all demand injected reaches ground). The gain stage then
  multiplies the flows that solve produced, per path it speeds. It never injects or removes current,
  so the conserved audit is untouched; a literal current amplifier inside the network would break
  conservation, which is why the gain lives at the chart change, after the solve.
- **G is relative and dimensionless**: `G = old cost / new cost`, from W2323's measured gate cost.
  Only a relative speed-up is invariant under changing the demand or velocity unit (an absolute
  conductance change is not), which settles the cold review's units point.
- **Value: the delivery cost SAVED, weighted by the demand waiting on what it speeds (v11, host
  ruling github:W146 Q1: OUTPUT is out).** For one accelerator X of gain G on card y, the saving is
  `(1 - 1/G) c_y`, weighted by y's demand and summed over the y's X speeds. This is the estimate the
  operator's L193949 names as the velocity input ("estimate its impact on that metric, and the change to
  that metric"). **Several accelerators on ONE card compose multiplicatively**: the joint saving is
  `(1 - 1/prod G) c_y`, not the sum of the separate savings; two gains of 2 save 3/4 of `c_y`, not all of
  it (github:R248; asserted in the appendix). **How the joint saving is CREDITED across its accelerators
  is OPEN**: a marginal credit (each accelerator's saving given the others) is the candidate, and the
  replay (nemik:W2393) settles it. The numbers are positive rationals with no 0 and no infinity: a
  near-no-op (G = 1.001) saves almost nothing, where v10's output reading gave it the full flow of the
  card it speeds. **v10's output and increment readings below are WITHDRAWN**; they stay as the witnesses
  of the forms this replaces (their assertions are in the appendix).
- **v10's cost-conditional reading, superseded.** A card's cost divides its value
  ("One scalar per card" below). Reading the accelerator's gain as multiplying its flow before that
  division, which is the stated reading and not a result (a velocity gain and a card's own cost are
  different quantities, and how they compose is open), an accelerator X (cost `c_X`) of a card y
  (flow F, cost `c_y`) is ahead of y WHEN
  `c_X <= G c_y` on the output reading, or `c_X <= (G - 1) c_y` on the increment reading, the F
  cancelling. That is sufficient, not exact: it is also necessary only when X's amplified flow is
  its largest reason. Under the hard maximum over a card's reasons an accelerator with demand of
  its own can lead past the threshold (own flow 3, G = 3/2, F = 1, `c_y` = 2 and `c_X` = 4, above
  the threshold 3, scores 3/2 against y's 1; asserted; v8 wrote "exactly when"). A cheap
  accelerator leads; a costly one pays for itself first. An UNCONDITIONAL
  velocity-first (100702) would be a named floor along accelerates edges, a rule, not a derived
  consequence: the operator's call. How several accelerators on one path compose (gains in series
  multiply?) is not settled here. G is a declared estimate before the accelerator lands (the typed
  speed-up edge, nemik:W2328) and a measurement after (W2323); the replay compares the two.
- **Velocity-first (v11, host ruling github:W146 Q2): L100702 STANDS, unconditional, until the replay
  says otherwise.** The exchange argument is correct arithmetic under the objective (the sum of demand
  times completion time). Take an accelerator X (cost `c_X`, demand of its own `w_X`) of a card y (cost
  `c_y`, demand `w_y`) with gain G, so y costs `c_y / G` once X is done. X first totals
  `w_X c_X + w_y (c_X + c_y / G)`; y first totals `w_y c_y + w_X (c_y + c_X)`. X first wins exactly
  when `c_X < (1 - 1/G) c_y + (w_X / w_y) c_y`. **For a PURE accelerator, whose value is only the
  speed-up (`w_X = 0`), that is the ruling's `c_X < (1 - 1/G) c_y`;** an accelerator with demand of its
  own leads past that threshold by `(w_X / w_y) c_y`, so the pure threshold is sufficient, not exact
  (asserted below). But applying it would override a standing OPERATOR rule with a HOST inference, which
  the host cannot do. v11 therefore keeps velocity-first unconditional and carries the conditional rule
  as a **REPLAY CANDIDATE** (nemik:W2393): if the replay shows it burns the backlog faster, that
  comparison goes to the operator as a ruling that looks wrong, with the numbers.
- **A broken gate is NOT `c_old = infinity` (v11, host ruling github:W146 Q1).** v10 took it as the
  limit `G -> infinity`, with an unbounded output that dominates. The design's numbers are positive
  rationals with no 0 and no infinity, so a broken gate stays covered by the existing gate rules (a red
  gate blocks the ledger), not by an infinite cost. v10's reading, for the record: the operator's
  "what's the velocity of a broken gate". Today's red-gate case is already edges
  (cold review, relayed: mtools `gate.py red()` blocks every open card on the gate card, with a
  named-repair exception that v6 read; mtools' code not read by me), so it needs no rule. W2039's round-check repairs are gate-band while the
  gate is GREEN, no gate card blocks anything on them, and the circuit does not rank them: they
  keep the tier through the shadow run until the replay shows the gain reproduces it.
- **Uniform velocity cannot reorder anything, and per-chain conductance scaling reorders only the
  DELAY, which is not ranked.** Scaling every conductance by v multiplies every potential by 1/v and
  leaves every current unchanged (so no order of currents, the pro rail, changes). Scaling ONE
  chain's conductances changes that chain's delay (witness: delays 18 and 8, velocity 3 on the slower
  chain makes 6, below 8) but also leaves its current unchanged (3 at v = 1 and at v = 3, in the
  appendix). v7 presented that as the reordering; the cold review is right that it reorders a
  quantity the ranking does not read, and that the gain model says velocity is not a conductance
  change. What reorders a RANKED quantity under the gain model is a gain that differs per
  accelerator: two accelerators of equal flow and equal cost with G = 2 and G = 3/2 rank in that
  order, and halving the second's cost flips it (appendix). "Velocity is the conductor" (188975) is
  then a gain stage in series with the paths it speeds, applied after the solve, not a factor on
  every conductance in it.

## Reading the rails: named external projections, never the logic

The operator (189606): the rails can be read as independent accumulators or as a differential
pair, "a wheatstone bridge can be used to translate between the two interpretations".

**What el-atlas forbids, which v8 did.** Its Law 3.1 (lines 228 to 235, verified at substrate
1673d08d2): the pair is "never quotiented to a ratio, an odds, a normalized probability, or any
single decision coordinate, by any operation of the logic"; "odds space is where one goes to
decide; it is not where the logic lives", and the collapse is admissible only as "an explicit,
external, named collapse". Lemma 3.2 (237 to 243): the quotient cannot tell both-high from
both-low, `q(a, a) = 1`. Law 4.2 (298 to 302): the bias "must not be read as a log-odds", for the
same reason. CX-1 (1231 to 1235) says the same of any odds reading. P-1 (1872 to 1877) records, as
the spec quotes it (I did not re-verify the line in a transcript; the cold review found no
operator utterance in host transcript 695f3e0a matching "odds", so v8's word had no ruling behind
it): "I don't (ever) default to thinking in odds; it's always a balance of evidence, not a
likelihood of outcome." What licenses a ranking at all is Law 3.1's "explicit, external, named
collapse" (line 235), CX-1's "external decision step" (1234 to 1235) and Remark 3.5's plurality
(261 to 270): every projection of the pair to a scalar is legitimate if it is "plural, external,
and named", never treated as THE value of the pair. (v9 also leaned on Remark 2.5c, and the cold
review is right that that misreads it: 2.5c's chart-image role means the ratio is half of an
INVERTIBLE (product, ratio) map where nothing is discarded; the ranking uses the ratio alone and
ties across mass, which is 2.5c's "as a value" role, the collapse, admissible only as the external
decision step.) v8 called its value the odds, in the logic's own words and against these laws.
v10 names its projections instead:
- **RANK, the order, is the bias projection: demand per unit of the card's own cost, `pro / cost`
  (times the constant `u0`). A ratio, said plainly, and a named external decision, a CHOICE.** It
  is `u0 x E+/E-`, order-identical to v8's odds and to `pn / cn` on every costed queue (the cold
  review's check on 200 cards), which is the differential reading of 189606 and the bias shadow in
  Remark 3.5's list. v9's words "not a ratio" and "reads the accumulator" were a relabel and are
  withdrawn: the con rail is the card's own cost, and the value divides by it. The projection is
  RATIO-BLIND by construction, Lemma 3.2's `q(a, a) = 1`: pro and cost of (4,4), (1,1) and (1/4,1/4)
  give one value. That is what a throughput order is. What it cannot say, the flags below say.
- **MASS is the product `pn cn`, by definition** (el-atlas Lemma 2.5b, line 177: "mass m = u+ +
  u-, the product E+ E- = exp(m)"; line 497, `c = u+ + u-`), read directly from the two rails, each
  divided by its own queue median (`pn` and `cn`, dimensionless). **It is NOT a bridge readout.**
  v8 said "mass is read from the SUPPLY: the product" and gave the bridge's supplies as 9 against
  1/9. The bridge's supply (gcalculus `bg`, `reduction.py` 551 to 556 at 1283876; the appendix's
  `bridge()[2]`) is 2 for (3,3) and 2/3 for (1/3,1/3), and for equal products 4 it is 23/17 at
  (4,1) and (1,4) but 3/2 at (2,2): not a function of the product. At balance it is `AND(pro, con) +
  AND(ref)`, v7's arm current plus a constant (the cold review; asserted). el-atlas 1350 ("the
  supply reads their sum - mass") is a structural correspondence the spec itself marks (line 1364,
  OB-5 for the strong form), not a license to read mass off this circuit. v7's geometric mean is
  only the half-sum of the logs, the square-root shadow of the product, never evaluated here; its
  derivation above concerns two quantities in one chart and one unit, not pro and con.
- **The FLAGS: four open quadrants against the medians (mine; the spec has no decoder policy).**
  `pn > 1, cn < 1` wanted and cheap; `pn > 1, cn > 1` BOTH, wanted and costly; `pn < 1, cn < 1`
  NEITHER, little demand and little cost; `pn < 1, cn > 1` unwanted and costly. Equivalently BOTH is
  `log m > |b|` with `b = log(pn / cn)` the log-ratio, and NEITHER is `log m < -|b|` (v9 wrote
  `|log b|`, a double log: the notation is fixed; the proof is the same, `m > pn/cn` iff `cn^2 > 1`,
  checked exactly on a grid in the appendix, where the bias is the ratio itself). The flags are
  routing, never an input to the order, and they are queue-relative: an unrelated arrival moves a
  median and can move a card's flag. That is accepted because they never touch the order; the
  order has no queue reference (below). **Their boundaries are stated, not left unread.** EVERY
  card whose rail EQUALS its median lies in no open quadrant and raises no flag, not only the
  median card: on a discrete scale ties are common (costs 1, 2, 2, 2, 3 leave three of the five
  cards at `cn = 1`; asserted), and an even count can give a median equal to card values. A ready
  card that lands no demand (nothing depends on it) has `pro = 0`, which is outside the carrier (no
  zero; the pro rail has NO evidence, absent and not zero): it takes value 0, no quadrant, and `pn`
  is undefined for it; the pro median is taken over the cards with `pro > 0`, and with none there
  are no flags. **That encoding is asymmetric, and the asymmetry is a CHOICE**: an absent pro is
  encoded as 0, the annihilator (the card sorts last whatever its cost), while an absent COST was
  encoded as the identity (gain 1). **v11 ends the cost half: an absent cost is not encoded at all, the
  card is excluded from the value ranking and routed to grooming (host ruling github:W146 Q3), so the
  asymmetry is gone; an absent PRO keeps its 0.** The 0 matches today's rows
  (`salience.get(ref, 0)`) so the regression holds, not because anything derives it. (The cold
  review counts about 10 of 420 ready cards in nemik with no open local waiter, ignoring
  cross-repo edges, so approximate and not fleet-wide.)
- **BOTH on a READY card means wanted and costly (v11, host ruling github:W146 Q6: BOTH routes to
  decomposition, no median-based route).** Pro is nonzero only where demand lands, the ground cards,
  which have no open prerequisite, so a BOTH card has no blocker to work (v7's "work its blocker" had
  nothing to act on). **Decomposition follows the absolute rules already in force: loop-prompt line 15 (a
  card that cannot finish in one tick is atomized) and nemik's OversizeShape.** Demand only ORDERS which
  of those cards are atomized first; it never decides whether one is, so there is no cut at the median
  (which flagged a fixed fraction of every queue whatever the absolute sizes, about half of the ready
  cards by construction). v10's "I route it to DECOMPOSITION ... OPEN: which cut, and whether to route
  at all" is answered. 189510's words "hasn't been groomed or decomposed" attach to a card that LACKS a
  cost, not to a costly one (v8's "the operator's own word for a costly card" misread it and is
  withdrawn). For a WAITING card "wanted and blocked" is not a reading of these rails (its pro is 0):
  its demand rides on its ready blockers, which the flow already lifts, and W2327's per-dependency
  current would give a through-current if a ranking ever wants one (OPEN). NEITHER routes to
  grooming or a probe. A cost-less card is not NEITHER: its con rail has no evidence (absent, not
  zero), el-atlas's N on that rail alone; v11 excludes it from the value ranking and routes it to
  grooming (Q3, above).
- **The bridge is the null and sign test only.** Put the card's rails as one divider (`g1 = pro`,
  `g2 = con`), the reference (the medians) as the other, with a coupling `g5` across the middle
  (balance `g1 g4 = g2 g3`; zero coupling current at balance). The DETECTOR is null EXACTLY at the
  reference ratio and has the sign of the bias, but its size off null mixes bias and scale ((4,1)
  and (8,2) share one ratio and read differently; appendix), and it is blind to scale ((3,3) and
  (1/3,1/3) are both null). The ordinary-chart ratio is read directly where a magnitude is wanted.
  The bridge is the operator's translator between the two readings (189606); it is not where mass
  or the order is read.
- **The decoder.** The spec has no policy; this is mine to state, and it is named, external and
  plural (line 235 "an explicit, external, named collapse - it is never the semantics"; line 1860
  "name every decoder"; Remark 3.5): RANK (the next section), MASS (the product), and the quadrant
  FLAGS above. None is the value of the pair.

## One scalar per card: demand per unit of the card's own cost, exact

RANK, the order, is `value = pro x u0 / cost`, with `u0` a cost unit (below): demand per unit of the
card's own cost, a ratio, the bias projection of the pair. It is a named external decision and a
CHOICE of this document, not a derivation from the rulings. It may be written as a gain
`G_cost = u0 / cost` applied to pro after the passive solve, but that is a way of writing the same
number, not a justification: v9 said it was "not a ratio" and "forced", and both are withdrawn.
- **Cost counts against** (189510, which warrants the SIGN and nothing more: the cold review is
  right that it gives no form). The factor is below 1 for a card dearer than the unit and above 1
  for a cheaper one, so the value rises with pro and falls with cost; the appendix asserts both signs.
  v7's reason `cost_c W_c / D_series` is withdrawn (above): it scored cost FOR a card. With it
  gone, every reason a card has is a flow in the one demand unit, so reasons compare without
  normalising each against its own total.
- **The exponent on cost is a CHOICE, k = 1.** Every `pn / cn^k` counts cost against and is
  unit-free yet orders differently ((4,2) against (3/2,1): k = 1 puts the first ahead, 2 against
  3/2; k = 2 puts the second ahead, 1 against 3/2), so k is a weight, and k = 1 is the doc's. The
  functional equation v9 offered, `f(c / G) = G f(c)` for every G > 0, does give `f(c) = f(u0) u0 /
  c`, but only because it is homogeneity of degree -1 in cost stated as a premise: the weight moved
  into the premise and did not go away (the cold review: it needs no continuity, but over a
  restricted set of gains, say only G = 2, a strictly decreasing non-power solution exists and
  reorders a pair; and `p^2 u0 / c` satisfies the cost clause and reorders too, so "a gain
  multiplies the value" is a second premise). No operator line warrants it. 189636 and 189692
  answer questions about the ACCELERATOR's value and neither mentions cost; and the `G = old cost /
  new cost` of the velocity section is W2323's MEASURED gate cost of the paths the accelerator
  speeds, a recurring per-landing cost, not the card's own con-rail cost (manifest or size) that
  this divides by. The two are different quantities, so "a velocity card cuts y's cost by G, with
  exactly the effect of the gain G on y" is withdrawn. Whether several gains on one path compose by
  multiplication is not settled: that is open for velocity against velocity (the velocity section),
  and equally open for the cost factor against a velocity gain; the appendix's accelerator
  thresholds use the product only as the stated reading, not as a result. The exponent belongs
  beside p under "not settled", for the operator to confirm.
- **The cost unit `u0` is a declared scale, a common factor for every costed card.** Changing it
  scales every costed card's value together and cannot change their order (asserted). It matters
  only for a card with no cost, whose factor is ABSENT (the identity: 1, as if its cost were `u0`),
  so each change of `u0` moves every cost-less card against every costed one (asserted: X, pro 1,
  cost 2, against cost-less Y, pro 3/4, puts Y ahead at u0 = 1 and X ahead at u0 = 2). It is
  specified as LEARNED from landing history, never a typed constant, the statistic unspecified
  (OPEN, "not settled"), and fixed between reviewed re-calibrations; the appendix stands in a typed
  value only to run the checks. It is NOT the queue median: v8's median moved with unrelated
  arrivals and reordered the cost-less card. Re-calibration moves it at a slower, reviewed cadence,
  which is the median's defect made rarer, not removed. It is a second declared scale beside the
  source-size table (below).
- **The projection is ratio-blind, and the order says nothing about mass.** (4,4), (1,1) and (1/4,1/4)
  at `u0 = 1` tie (asserted); ties go to the card symbol in a declared order, never a tolerance.
  Whether mass should break such a tie is OPEN; the flags distinguish them (BOTH, none, NEITHER).
- **Regression, and the intended change.** With every costed card's cost EQUAL TO `u0` (so a
  cost-less card, whose cost is taken at `u0`, is one of them) and no gain, the order is EXACTLY
  today's salience order (the pro rail is nemik.flow unchanged; ties by symbol, as `compose` falls
  back). If the costed cards share a cost `c` other than `u0` and any cost-less card exists, it
  does NOT hold: at u0 = 1, X (pro 1, cost 3) against cost-less Y (pro 1/2) puts Y ahead, where
  salience puts X ahead (asserted). It is today's SALIENCE order, not today's
  rank order, which also holds the gate tier, bands and fronts: removing those is the intended
  change. With UNEQUAL costs the order is by demand per unit cost, which is what the operator's
  framing asked for ("what counts against a ready card"), not a regression: today E1 (11/10) leads
  E2 (1); at costs 10 and 1 E2 leads (appendix). v7's fixture "cards with no velocity role keep
  their relative order" is restated to what holds: it holds at equal cost, and the replay counts
  the pairs that flip at the measured costs, for the operator to see. NOT claimed: that a
  cost-less card keeps its place among unequal costs.
- **Paths add; reasons do not.** Within the circuit, currents of parallel paths add by Kirchhoff
  (p = 1, exact, conserved). That is the right law for PATHS and the wrong one for REASONS: a card's
  reasons (the demand it serves; for an accelerator, the flow it amplifies) are different kinds, and
  a sum lets many weak ones overtake one strong one (the operator's "don't make it linear", 188939).
  The parameter-free combination is the HARD MAXIMUM of a card's reasons, the `tau -> 0` limit of
  the soft maximum `tau log sum exp(u_i/tau)`; ties go to the card symbol in a declared order, never
  to a tolerance. The soft maximum at a finite `p = 1/tau` (ordering-equivalent to `sum x_i^p`,
  exact for integer p; `max <= tau LSE <= max + tau ln n`) lets breadth break near-ties.
- **p is OPEN, and v7's derivation of it is withdrawn.** v7 took the smallest integer p with
  `r^p >= kmax`, r the median ratio of adjacent hard maxima. Its failures, from the cold review,
  each now checked: the text said kmax = 3 and the appendix used 2; it guarantees only gaps of at
  least r, so about half the adjacent gaps (those below the median) can be overturned; in dense
  queues r approaches 1 and p climbs (r = 1.023 gives p = 49, r = 1.01 gives p = 111, effectively
  the hard maximum with huge exact Fractions); and p depends on the whole queue, so an unrelated
  arrival that moves r from 2 to 3/2 flips two other cards (the pair one reason of 1/2 against two
  of 1/3: p = 1 for r = 2, p = 2 for r = 3/2). Until the replay finds a p that holds, the hard
  maximum above is the design, and nothing here claims a derived exponent.
- **An urgency source's size.** Today the sources are declared data (class weights 1, 2, 8, 15 in
  `rank-weights.toml`, calibrated at W249). The vector enters the ranking only through the band, the
  layer being removed; a vector-to-source-size mapping would be a new declared table, calibrated and
  replayed. With the cost unit `u0` above that makes TWO declared scales, not one (v8 and v9 said
  "the ONE place a declared scale remains" here and also added `u0`: contradictory, fixed). Stated,
  not hidden.

## Precedences, the floor, the cycle

Only what is not a matter of speed stays a hard constraint: the trust-boundary policy block
(`bands.toml [[policy]]`, safety); umbrellas excluded (`is_umbrella`, structure); the fleet
burn-down tier across repos (the operator's order); the round check (a process rule that follows
the ranking; **unverified**, known from its refusals).
- **The critical floor: NO floor, only a larger demand source (v11, host ruling github:W146 Q4).**
  The bands survive only as DISPLAY labels (188832, 188919); hard safety stays in the separate
  trust-boundary policy block above, which is the list of hard constraints; a critical card gets its
  priority from a larger demand source in the one declared table below, not from a band that outranks
  the ranking. v10 left this OPEN: `bands.toml [guarantee]` / `nemik-rank --check` count tag bands as
  above the floor, and the inversion persisted (a vector-critical card with demand 6 or 11 behind a card
  of demand 12 still trips `--check`; relayed). **The SIZE of the source is OPEN**: calibrate it by the
  replay (nemik:W2393), with fixture B as the acceptance test and `nemik-rank --check` redefined to
  match (it asserts the source, not a band floor). Until the replay, the interim definition stands and
  nothing here claims fixture B passes.
- **The velocity tag stays as a compatibility floor** for the cards that hold it today, retiring
  card by card when a card declares what it speeds (a typed field, nemik:W2328) or has a measured
  effect, so velocity-first (100702) does not lapse by the migration. v11 answers what replaces it:
  the value is the delivery cost saved (Q1), and velocity-first stays an unconditional rule (Q2).
- **W993's paydown lift** (`score.py tagged_band`) becomes a demand source at the paydown cards, the
  pace verdict as owed demand (the operator's 92679 and 93406, warranted on W986); the lift stays
  until then.
- **A cycle has no ground** (cold check D case 3, W2212): the carrier has no solution and all its
  demand strands on today's code (the cold review ran nemik.flow 485ce8f2: salience empty, the
  cards stranded), because red() blocks the chain card (relayed), so the deadlock exists today.
  Typing its cards BOTH is a DECLARATION, not a reading: their pro is 0 (stranded), so no reading
  of the rails makes them BOTH. **That stays unresolved** (the cold review's #51, open since v6).
  What can be said is structural: a component that holds demand and has no ground is wanted and
  blocked by the shape of the graph alone, and it should route to breaking the cycle and never be
  ranked; whether that is a rail value or only a fact about the graph is OPEN. It needs a `red()`
  change (mtools) or a typed cycle-break, carded as nemik:W2329 (queued at 4c49a41d with W2326 to
  W2328, which v7's cold review found absent at 5dd136de). **The gate-chain pull-in is a separate
  matter**: its reason is a green-gate repair waiting behind lower-ranked work (the v5 pass's N45,
  which I did not read), independent of any cycle, so it stays until the replay shows the circuit
  reproduces that case, not until W2329 lands (v7 tied the two without support).

## Migration

A dependency stays ONE relation with two views; every existing edge takes g = 1, no gain, so
nothing is rewritten. A coefficient is added, not an edge kind: an optional per-edge g (the override
`flow.solve` takes) and a gain, declared or measured. A speed-up gets its own typed edge, a new card
field owned by the writer (nemik:W2328), so it is never read as a dependency. The regression property
gates the migration; the gate tier and the velocity tag stay through the shadow run; each per-repo
flip is a reviewed diff.

## Fixtures the build must pass

Relayed from github-00's cold passes (`v5check/` to `v7check/`; I read the v7 review and the case
lines of its check script, not the earlier ones). None is claimed passed: each is a test the build
must pass.
- **A: an accelerator is not ranked behind the card it speeds.** v7 claimed this for ANY gain above 1
  from the output reading, and the cold review showed it fails once cost counted for the card, and
  that the choice of the output was made by the fixture. v9: it holds WHEN `c_X <= G c_y` (output)
  or `c_X <= (G - 1) c_y` (increment), exactly so only when X's amplified flow is its largest
  reason; an unconditional version is a floor rule, the operator's call (the velocity section).
  This fixture is therefore NOT a theorem of the design.
- **B: UNSCORED cards (no vector; `bands.toml` `unscored = "normal"`) do not break the order.** v7
  re-read it as "ungroomed", which is about cost, a different thing: an unscored card with a cost is
  ranked. v11 (Q4): there is no floor to invert, so this fixture is the ACCEPTANCE TEST of the larger
  demand source's size (the floor bullet), run by the replay.
- **C: no front-width collapse** (there are no fronts); the unsolved choice that used to decide the
  order now sits in p, which is OPEN.
- **D: the red-gate cases**, on nemik.flow 485ce8f2 per the cold review's check script: case 1, a
  gate chain lands its demand on the repair card (salience `{R: 3}`); case 2, a ready gate card
  absorbs its two waiters' demand (`{G: 2}`; v7 did not state it); case 3, a cycle strands all of it
  (salience empty): the unresolved one.
- **Regression:** with every g = 1, no gain, and every costed card's cost EQUAL TO the cost unit
  `u0` (a cost-less card is then one of them) the new solver reproduces today's SALIENCE order
  EXACTLY for every card of every repo (by construction: pro is nemik.flow unchanged and the cost
  factor is then one common factor). A common cost other than `u0` with any cost-less card
  present departs from it (X, pro 1, cost 3, against cost-less Y, pro 1/2, at u0 = 1: Y leads;
  asserted). It is not today's rank order (gate tier, bands and fronts), whose removal is the
  intended change. W2727 rises (relayed). Cards with no velocity role keep their relative order
  **at equal cost only**; at unequal cost the order is by demand per unit cost, an intended change
  the replay measures (the "One scalar per card" section). v7 claimed the stronger form and the
  cold review showed it false; v8 added a median-cost clause for cost-less cards that was also
  false, and is withdrawn.

## What is not settled

- **Settled by the host ruling github:W146 (v11), kept here as what the replay (nemik:W2393) can
  still change:** output or increment is answered (the value is the delivery cost saved, Q1; the
  credit across several accelerators of one card is OPEN, a marginal credit the candidate); velocity
  first stays unconditional (Q2), the conditional rule a replay candidate; the cost-less card leaves
  the value ranking for grooming (Q3, with nemik:W2360 and W2392); no median route to decomposition
  (Q6); no critical floor, only a larger demand source (Q4; its SIZE is open); k = 1 and the objective
  are named external choices (Q5).
- **The cost's numeric scale and the cost unit `u0`** (derived from landing history, measured, not
  typed; a declared scale between reviewed re-calibrations) and how a size or manifest becomes a
  cost.
- **The order itself: demand per unit of the card's own cost, `pro / cost`, k = 1.** The doc's
  CHOICE, admissible as a named external decision, order-identical to v8's odds, the bias
  projection. No operator line gives the form, and the premise v9 offered for k = 1 was degree -1
  homogeneity restated; github-00 puts the decision to the operator.
- **Whether mass breaks a tie** in the order (the projection is ratio-blind), and **the cut for the
  flags**: the queue's medians (queue-relative, a fixed fraction flagged) or declared units. (Whether
  BOTH routes to decomposition is answered by Q6: it does, by the absolute rules, never by a cut.)
- **p**, the exponent of the soft maximum across a card's reasons: no derivation survives. The hard
  maximum stands in.
- **The size of the larger demand source** that replaces the critical floor (v11, Q4: no floor): a
  declared table, calibrated and replayed (nemik:W2393), with fixture B the acceptance test and
  `nemik-rank --check` redefined to match.
- **The cycle** (#51): its cards cannot be read BOTH from the rails; the typed answer is a
  declaration, nemik:W2329. A waiting card's "wanted and blocked" reading needs W2327's through-current.
- **How several accelerators on one path compose**, and whether G is estimated before landing and
  measured after (nemik:W2328, W2323).
- The open gate card as a typed fact (nemik:W2326); `flow.py` returning the per-cone quantities
  (nemik:W2327).
- Everything marked relayed above.

## Steps, smallest first

1. This design through the warm and cold reviews; the operator is informed.
2. The cost estimates (nemik:W2360: a derived own cost by a reference class from measured landings,
   the card's own estimate overriding it, one error series with a learned freshness rule) and the shape
   that warns on a ready card with none (nemik:W2392): the prerequisite of Q3's route.
3. The regression test, the appendix checks as tests, and `flow.py` returning the quantities.
4. The cost scale from landing history; the typed speed-up edge.
5. The replay over the fleet and landed history (nemik:W2393: the ruled order against today's bands, Q1's
   credit rule, Q2's conditional rule, Q4's source size, Q5's heuristic gap), then the shadow run, then
   the per-repo flip.

## Appendix: the exact checks

Run with exact `Fraction`s and no floats. Every assertion held. The block below is extracted
mechanically from this document (the text between the first python fence and its close) and executed
as written; the scratch file it was written in is not the artifact, this block is. Where an
assertion witnesses a FAILURE of an earlier claim (the sign of v7's cost term, v7's arm-current mass,
v7's p), it says so.

```python
from fractions import Fraction as F
from itertools import product
from math import isqrt, prod

# ---- the carrier: NOT, OR (parallel conductances add), AND (series, half the harmonic mean) ----
NOT = lambda x: 1 / x
OR = lambda a, b: a + b
AND = lambda a, b: a * b / (a + b)

for a, b in product((F(2), F(1, 3), F(11, 5)), repeat=2):
    assert AND(a, b) == NOT(OR(NOT(a), NOT(b)))  # De Morgan: AND is NOT(OR(NOT, NOT))
    assert OR(a, b) == NOT(AND(NOT(a), NOT(b)))
    assert NOT(NOT(a)) == a
# a parallel connection of two conductances is a parallel connection of their resistances: the
# same topology read in the other chart, not a series one
g1, g2 = F(2), F(3)
assert NOT(OR(g1, g2)) == AND(NOT(g1), NOT(g2))


# ---- exact nodal solve on a small network, with a set of ground nodes ----
def gauss(mat, rhs):
    n = len(rhs)
    aug = [row[:] + [rhs[i]] for i, row in enumerate(mat)]
    for c in range(n):
        p = next(r for r in range(c, n) if aug[r][c] != 0)
        aug[c], aug[p] = aug[p], aug[c]
        aug[c] = [x / aug[c][c] for x in aug[c]]
        for r in range(n):
            if r != c and aug[r][c] != 0:
                f = aug[r][c]
                aug[r] = [x - f * y for x, y in zip(aug[r], aug[c])]
    return [aug[i][n] for i in range(n)]


def potentials(edges, ground, inject):
    nodes = sorted({n for e in edges for n in e} | set(inject))
    free = [n for n in nodes if n not in ground]
    ix = {n: i for i, n in enumerate(free)}
    lap = [[F(0)] * len(free) for _ in free]
    for (u, v), g in edges.items():
        for x, y in ((u, v), (v, u)):
            if x in ix:
                lap[ix[x]][ix[x]] += g
                if y in ix:
                    lap[ix[x]][ix[y]] -= g
    phi = gauss(lap, [inject.get(n, F(0)) for n in free])
    out = {n: F(0) for n in ground}
    out.update({n: phi[ix[n]] for n in free})
    return out


def delay(edges, ground, inject):
    phi = potentials(edges, ground, inject)
    return sum(d * phi[n] for n, d in inject.items())


# ---- one dependency DAG: A (demand 5) needs C; B (demand 3) needs C and E; C needs F; E, F ready ----
DEP = {("A", "C"): F(1), ("B", "C"): F(1), ("B", "E"): F(1), ("C", "F"): F(1)}
DEMAND = {"A": F(5), "B": F(3)}
CONE_A = {k: g for k, g in DEP.items() if k[0] in ("A", "C")}
CONE_B = {k: g for k, g in DEP.items() if k[0] in ("B", "C")}
d_a = delay(CONE_A, {"F"}, {"A": DEMAND["A"]})
d_b = delay(CONE_B, {"E", "F"}, {"B": DEMAND["B"]})
d_global = delay(DEP, {"E", "F"}, DEMAND)
assert (d_a, d_b) == (50, 6)
assert d_a + d_b == 56 and d_global == F(173, 3) and d_global != d_a + d_b  # leak across cones
# nemik.flow solves each source on its OWN cone (direction is the queue's), so the marginals below
# are per cone and are summed over the cones that contain the card.

# node grounding per cone: D - D' = phi_c^2 / M_cc
for cone, ground, src in ((CONE_A, {"F"}, "A"), (CONE_B, {"E", "F"}, "B")):
    phi = potentials(cone, ground, {src: DEMAND[src]})
    m_cc = potentials(cone, ground, {"C": F(1)})["C"]
    before = delay(cone, ground, {src: DEMAND[src]})
    after = delay(cone, ground | {"C"}, {src: DEMAND[src]})
    assert before - after == phi["C"] ** 2 / m_cc

# ---- the derivative is not the discrete change, and it misranks ----
def edge_marginal(edges, ground, inject, edge, rho):
    """Exact D - D' when `edge`'s conductance rises by the RELATIVE speed-up rho."""
    changed = dict(edges)
    changed[edge] = edges[edge] * (1 + rho)
    return delay(edges, ground, inject) - delay(changed, ground, inject)


rho = F(10)
chain = {("s", "m"): F(1), ("m", "g"): F(1)}  # edge s-m alone between s and m
inj1 = {"s": F(3)}
# network 2: the same edge s-m (conductance 1) with a two-hop path s-x-m of conductance 10 each in
# parallel, so the effective resistance across s-m is 1/6, not 1: the edge is one of several paths
par = {("s", "m"): F(1), ("s", "x"): F(10), ("x", "m"): F(10), ("m", "g"): F(1)}
inj2 = {"s": F(17)}
e1 = e2 = ("s", "m")
phi1 = potentials(chain, {"g"}, inj1)
phi2 = potentials(par, {"g"}, inj2)
drop1 = phi1["s"] - phi1["m"]
drop2 = phi2["s"] - phi2["m"]
deriv1 = rho * chain[e1] * drop1**2
deriv2 = rho * par[e2] * drop2**2
disc1 = edge_marginal(chain, {"g"}, inj1, e1, rho)
disc2 = edge_marginal(par, {"g"}, inj2, e2, rho)
assert deriv1 > deriv2 and disc1 < disc2  # derivative ranks e1 first, the exact change ranks e2 first
print("derivative", deriv1, deriv2, "discrete", disc1, disc2)
# the exact form: Sherman-Morrison with Reff the effective resistance across the edge's ends
reff2 = potentials(par, {"m"}, {"s": F(1)})["s"]  # unit current in at s, out at m: phi_s = Reff
delta = rho * par[e2]
assert disc2 == delta * drop2**2 / (1 + delta * reff2)
assert drop2**2 / reff2 - disc2 == drop2**2 / (reff2 * (1 + delta * reff2))  # shorting is the limit

# ---- gain: solve first (passive, conserved), then amplify the flows the solve produced ----
phi_a = potentials(CONE_A, {"F"}, {"A": DEMAND["A"]})
phi_b = potentials(CONE_B, {"E", "F"}, {"B": DEMAND["B"]})
into_a = DEP[("C", "F")] * (phi_a["C"] - phi_a["F"])  # current through C-F in A's cone
into_b = DEP[("C", "F")] * (phi_b["C"] - phi_b["F"])  # and in B's cone
assert (into_a, into_b) == (5, 1)
assert into_a == DEMAND["A"]  # the passive solve conserves demand: all of A's demand reaches F
assert DEP[("B", "E")] * (phi_b["B"] - phi_b["E"]) + into_b == DEMAND["B"]  # and all of B's reaches E or F
flows, gains = [into_a, into_b], [F(2), F(2)]  # an accelerator that doubles the conduction of C-F
output = sum(g * x for g, x in zip(gains, flows))  # sum of exp(u_i + log G_i): logsumexp partially applied
increment = sum((g - 1) * x for g, x in zip(gains, flows))
assert (output, increment) == (12, 6)  # exact: no exp or log is ever evaluated
# on flow alone, a gain 3/2 on a card holding flow 1 gives an output of 3/2 (ahead of the card) and an
# increment of 1/2 (behind it). No ruling chooses between them, so this does NOT decide fixture A:
# with cost the question is the cost thresholds asserted below, for either reading
assert (F(3, 2) - 1) * F(1) < F(1) < F(3, 2) * F(1)

# ---- velocity as a CONDUCTANCE reorders only the delay D, which is not ranked (currents: below) ----
def d_chain(i, v):
    return delay({("s", "m"): v, ("m", "g"): v}, {"g"}, {"s": i})


x, y = F(3), F(2)
assert d_chain(x, 1) > d_chain(y, 1)
assert (d_chain(x, F(7)) > d_chain(y, F(7))) == (d_chain(x, 1) > d_chain(y, 1))  # uniform: same delay order
assert d_chain(x, F(3)) < d_chain(y, 1)  # v on one chain only: the DELAYS flip order (D is not ranked)

# ---- the con rail: series, cost adds, closure counted once ----
COST = {"A": F(1), "B": F(1), "C": F(2), "E": F(4), "F": F(3)}
CLOSURE = {"A": {"A", "C", "F"}, "B": {"B", "C", "E", "F"}}
con = lambda s, cost: sum(cost[c] for c in CLOSURE[s])
d_series = sum(DEMAND[s] * con(s, COST) for s in DEMAND)
assert (con("A", COST), con("B", COST), d_series) == (6, 10, 60)
need = lambda c: sum(DEMAND[s] for s in DEMAND if c in CLOSURE[s])  # the demand that needs c
for c in "CEF":  # finishing c removes its cost from every closure that holds it: exact, linear
    after = {k: (v if k != c else F(0)) for k, v in COST.items()}
    assert d_series - sum(DEMAND[s] * con(s, after) for s in DEMAND) == COST[c] * need(c)
slower = dict(COST)
slower["C"] -= 1  # a velocity card that cuts C's cost by 1
assert d_series - sum(DEMAND[s] * con(s, slower) for s in DEMAND) == 1 * need("C")

# ---- independence of the rails, on READY cards (pro is the current absorbed where demand lands) ----
t1 = {("T1", "P"): F(1)}  # T1 needs P alone
t2 = {("T2", "Q"): F(1), ("T2", "Q2"): F(1)}  # T2 needs Q and Q2
t3 = {("T3", "R"): F(1), ("T3", "R2"): F(1)}  # T3 needs R and R2
absorbed = lambda edges, ground, src, card: edges[(src, card)] * potentials(edges, ground, {src: F(1)})[src]
pro = {
    "P": absorbed(t1, {"P"}, "T1", "P"),
    "Q": absorbed(t2, {"Q", "Q2"}, "T2", "Q"),
    "R": absorbed(t3, {"R", "R2"}, "T3", "R"),
}
cost = {"P": F(2), "Q": F(2), "R": F(4)}
assert pro == {"P": F(1), "Q": F(1, 2), "R": F(1, 2)}
assert cost["P"] == cost["Q"] and pro["P"] != pro["Q"]  # same con, different pro
assert pro["Q"] == pro["R"] and cost["Q"] != cost["R"]  # same pro, different con
# "D can rise" belongs to the parallel (pro) chart; the series (con) chart only falls
s2 = {("S2", "Q1"): F(1), ("S2", "Q2"): F(1)}
assert delay({("S2", "Q2"): F(1)}, {"Q2"}, {"S2": F(1)}) > delay(s2, {"Q1", "Q2"}, {"S2": F(1)})
for c in "CEF":  # the series chart: finishing any card only lowers every closure that holds it
    done = {k: (v if k != c else F(0)) for k, v in COST.items()}
    assert all(con(s, done) <= con(s, COST) for s in DEMAND)
assert con("A", {**COST, "C": F(0)}) == 4 < con("A", COST) == 6

# ---- why the geometric mean: symmetric and self-dual (m(a,b) = a f(b/a)) force f(x)^2 = x ----
sq = lambda x: F(isqrt(x.numerator), isqrt(x.denominator))
geo = lambda a, b: sq(a * b)
for a, b in ((F(4), F(9)), (F(1, 4), F(9, 16))):
    assert geo(a, b) == geo(b, a) and geo(NOT(a), NOT(b)) == NOT(geo(a, b)) and geo(2 * a, 2 * b) == 2 * geo(a, b)

# ---- RANK: demand per unit of the card's own cost, pro * u0 / cost: a RATIO, a named external choice ----
def value(pro_, cost_, u0):
    """pro * u0 / cost: below 1 per unit of pro for a card dearer than the cost unit u0."""
    return pro_ * (u0 / cost_)


u0 = F(2)  # a typed stand-in so the checks run; the design LEARNS u0 from landing history
assert value(F(1, 2), F(1), u0) > value(F(1, 2), F(10), u0)  # same pro: the cheaper card first
assert value(F(1), F(2), u0) > value(F(1, 2), F(2), u0)  # same cost: the order is by pro, today's
# it IS the ratio: u0 * pro / cost, order-identical to v8's pro / (cost / median) and to pn / cn
for p_, c_ in product((F(1, 4), F(1, 2), F(1), F(3, 2), F(4)), (F(1), F(2), F(7, 4), F(5), F(10))):
    assert value(p_, c_, u0) == u0 * p_ / c_
grid = [(p_, c_) for p_ in (F(1, 4), F(1, 2), F(1), F(3, 2), F(4)) for c_ in (F(1), F(2), F(7, 4), F(5), F(10))]
v8_odds = lambda pc: pc[0] / (pc[1] / F(2))  # v8: pro / (cost / median cost), median 2
pn_cn = lambda pc: (pc[0] / F(3, 2)) / (pc[1] / F(5, 3))  # pn / cn with the medians of one queue
by = lambda f: sorted(grid, key=lambda pc: (-f(pc), pc))
assert by(lambda pc: value(pc[0], pc[1], F(7))) == by(v8_odds) == by(pn_cn)  # one order, three names
# the order of COSTED cards cannot depend on the cost unit: u0 is one common factor
queue = {"a": (F(3, 2), F(4)), "b": (F(1, 2), F(1)), "c": (F(1, 4), F(2)), "d": (F(1), F(3))}
order = lambda u0: sorted(queue, key=lambda k: (-value(*queue[k], u0), k))
assert order(F(1)) == order(F(2)) == order(F(7)) == ["b", "a", "d", "c"]
# the exponent on cost, k = 1, is a CHOICE. The equation f(c/G) = G f(c) for EVERY G holds of u0/c and
# of no other power c^-k, but it is degree -1 homogeneity stated as a premise: the weight moved
for g_ in (F(2), F(3, 2)):
    assert value(F(1), F(6) / g_, u0) == g_ * value(F(1), F(6), u0)
    assert (F(6) / g_) ** -2 != g_ * F(6) ** -2  # k = 2 breaks it
x_, y_ = (F(4), F(2)), (F(3, 2), F(1))  # (pro, cost); the hidden weight: k = 1 and k = 2 disagree
assert x_[0] / x_[1] > y_[0] / y_[1] and x_[0] / x_[1] ** 2 < y_[0] / y_[1] ** 2


# ... and over a RESTRICTED set of gains (only G = 2) a strictly decreasing non-power solution exists
# and reorders a pair (the cold review's check 2)
def m2(c):
    while c >= 2:
        c /= 2
    while c < 1:
        c *= 2
    return c


f_res = lambda c: (1 + (m2(c) - 1) / 4) / c
assert all(f_res(c / 2) == 2 * f_res(c) for c in (F(3), F(7, 4), F(5, 3), F(1)))  # f(c/2) = 2 f(c)
assert f_res(F(1)) > f_res(F(7, 4)) > f_res(F(2)) and f_res(F(7, 4)) == F(19, 28)  # and it falls with cost
assert F(3, 5) / F(1) > F(1) / F(7, 4) and F(3, 5) * f_res(F(1)) < F(1) * f_res(F(7, 4))  # u0/c: A' leads; f: B
# ... and p^2 u0 / c satisfies the cost clause too, and reorders (3,2) against (1,1/2): "a gain multiplies
# the VALUE" is a second premise
sq_cost = lambda p_, c_: p_**2 * u0 / c_
assert sq_cost(F(1), F(6) / 2) == 2 * sq_cost(F(1), F(6))  # the cost clause holds
assert sq_cost(F(3), F(2)) > sq_cost(F(1), F(1, 2)) and value(F(3), F(2), u0) < value(F(1), F(1, 2), u0)
# a cost-less card has an ABSENT cost factor (the identity): cost u0
assert value(F(5, 7), u0, u0) == F(5, 7)
# an absent PRO is encoded as 0, the annihilator, and an absent COST as the identity: an asymmetry that
# is a CHOICE (it matches today's salience.get(ref, 0)), not a derivation
assert value(F(0), F(1, 100), u0) == 0 < value(F(1, 10**6), F(10**6), u0)  # a no-demand card sorts last at any cost
# the projection is ratio-blind (el-atlas Lemma 3.2): equal pro/cost ties whatever the mass
assert value(F(4), F(4), F(1)) == value(F(1), F(1), F(1)) == value(F(1, 4), F(1, 4), F(1))
# v7 scored the work REMOVED, cost * W / D_series, which GROWS with cost: the wrong sign. Two cards of
# equal demand (W = 1) at costs 1 and 10 scored 1/11 and 10/11, the dearer card first
cw = {"cheap": F(1) * 1, "dear": F(10) * 1}
v7_term = {c: x / sum(cw.values()) for c, x in cw.items()}
assert (v7_term["cheap"], v7_term["dear"]) == (F(1, 11), F(10, 11)) and v7_term["dear"] > v7_term["cheap"]
# and per unit of its own cost it is W_c, the demand whose closure holds c: the UNSPLIT demand, which
# is NOT what the flow carries (the flow carries the split, conserved current each ground card absorbs)
assert all(x / {"cheap": F(1), "dear": F(10)}[c] == 1 for c, x in cw.items())
assert (need("E"), need("F")) == (3, 8)  # W_E = 3, W_F = 8 (appendix DAG)
pro_e = DEP[("B", "E")] * (phi_b["B"] - phi_b["E"])  # what E absorbs from B's demand
pro_f = into_a + into_b  # what F absorbs from A's and B's
assert (pro_e, pro_f) == (2, 6) and (pro_e, pro_f) != (need("E"), need("F"))  # absorbed 2 and 6, not 3 and 8
assert pro_e + pro_f == sum(DEMAND.values())  # the split is conserved: 8 in, 8 absorbed
# an accelerator X of one card y (flow F=1, cost cy) with gain G and cost cx, whose largest reason is
# its amplified flow, is ahead of y WHEN cx <= G * cy (it pays for its own cost): not unconditionally
G, cy = F(3, 2), F(2)
ahead = lambda cx: value(G * 1, cx, u0) >= value(F(1), cy, u0)
assert ahead(F(2)) and ahead(G * cy) and not ahead(F(4))
# ... but only sufficient: under the hard maximum an accelerator with demand of its own (flow 3) leads
# past the threshold: cx = 4 > G * cy = 3, value 3/2 against y's 1 at u0 = 2
own = max(F(3), G * 1)
assert F(4) > G * cy and value(own, F(4), u0) == F(3, 2) and value(F(1), cy, u0) == 1
# the median stand-in of v8 for a cost-less card FAILS: a cost-less U overtakes V, and an unrelated
# arrival N moves the median (2 to 3) and moves U from first to third
cq = {"V": (F(3, 2), F(4)), "U": (F(1), None), "W": (F(1, 2), F(1)), "Z": (F(1, 4), F(2))}
costs = lambda q: sorted(c for _, c in q.values() if c is not None)
med_of = lambda q: (costs(q)[len(costs(q)) // 2 - 1] + costs(q)[len(costs(q)) // 2]) / 2 if len(costs(q)) % 2 == 0 else costs(q)[len(costs(q)) // 2]
rank_at = lambda q, u0: sorted(q, key=lambda k: (-value(q[k][0], q[k][1] if q[k][1] is not None else u0, u0), k))
assert med_of(cq) == 2 and rank_at(cq, med_of(cq)) == ["U", "W", "V", "Z"]  # today's order was V U W Z
cq2 = dict(cq, N=(F(1, 100), F(10)))
assert med_of(cq2) == 3 and rank_at(cq2, med_of(cq2)) == ["W", "V", "U", "Z", "N"]  # U fell from first to third
# a FIXED unit u0 cannot do that: the relative order of the old cards is the same with and without N
assert [k for k in rank_at(cq2, F(2)) if k != "N"] == rank_at(cq, F(2))
# ... but u0 itself moves a cost-less card against a costed one: X (pro 1, cost 2) against cost-less Y
# (pro 3/4): Y leads at u0 = 1, X leads at u0 = 2 (each re-calibration does this to every such pair)
xy = {"X": (F(1), F(2)), "Y": (F(3, 4), None)}
assert rank_at(xy, F(1)) == ["Y", "X"] and rank_at(xy, F(2)) == ["X", "Y"]
# the regression holds when every costed card's cost EQUALS u0 (a cost-less card is then one of them) ...
reg = {"X": (F(1), F(3)), "Y": (F(1, 2), None)}
assert rank_at(reg, F(3)) == ["X", "Y"]  # salience order: X (1) before Y (1/2)
# ... and does NOT when the common cost c differs from u0 and a cost-less card exists: cost 3, u0 = 1
assert rank_at(reg, F(1)) == ["Y", "X"]
# every card whose rail EQUALS the median is unflagged, not only the median card: costs 1, 2, 2, 2, 3
costs5 = [F(1), F(2), F(2), F(2), F(3)]
med5 = sorted(costs5)[len(costs5) // 2]
cns = [c / med5 for c in costs5]
assert med5 == 2 and sum(1 for c in cns if c == 1) == 3  # three of the five cards sit exactly at cn = 1
assert all(not (pn_ > 1 and cn_ > 1) and not (pn_ < 1 and cn_ < 1) for pn_ in (F(2), F(1, 2)) for cn_ in cns if cn_ == 1)

# ---- p is OPEN: witnesses that v7's derivation (smallest p with r^p >= kmax) fails ----
def derive_p(ratio, kmax):
    p = 1
    while ratio**p < kmax:
        p += 1
    return p


soft = lambda xs, p: sum(x**p for x in xs)
assert derive_p(F(3, 2), 3) == 3 and derive_p(F(3, 2), 2) == 2  # the text said kmax 3, the appendix used 2
assert derive_p(F(1023, 1000), 3) == 49 and derive_p(F(101, 100), 3) == 111  # dense queues: p climbs
r2 = derive_p(F(2), 3)
assert r2 == 2 and soft((F(3, 2),), r2) < soft((F(1), F(1), F(1)), r2)  # a gap of 3/2 (< r) is overturned
one, two_ = (F(1, 2),), (F(1, 3), F(1, 3))
assert derive_p(F(2), 2) == 1 and soft(two_, 1) > soft(one, 1)  # r = 2: p = 1, the two weak reasons win
assert derive_p(F(3, 2), 2) == 2 and soft(one, 2) > soft(two_, 2)  # r = 3/2: p = 2, the strong one wins

# ---- the Wheatstone bridge (gcalculus gcalc/families/network/reduction.py:551-556 at 1283876) ----
def bridge(g1, g2, g3, g4, g5):
    a, b, c, d = g1 + g2 + g5, -g5, -g5, g3 + g4 + g5
    det = a * d - b * c
    va = (g1 * d - b * g3) / det
    vb = (a * g3 - g1 * c) / det
    return va, vb, g1 * (1 - va) + g3 * (1 - vb), g5 * (va - vb)


ref = (F(1), F(1))  # the reference arm: the queue's own median pro and con
for pro_, con_ in ((F(1), F(1)), (F(3), F(3)), (F(1, 3), F(1, 3)), (F(4), F(4)), (F(3), F(1))):
    detector = bridge(pro_, con_, *ref, F(1))[3]
    assert (detector == 0) == (pro_ / con_ == ref[0] / ref[1])  # null exactly at the reference ratio
# the detector is blind to scale: (3, 3) and (1/3, 1/3) are both null. MASS is therefore NOT read from
# it, and not from the bridge's supply either: the mass coordinate is the PRODUCT by definition
# (el-atlas Lemma 2.5b, line 177). The supply of the cited bridge is bridge()[2]; it is not a function
# of the product: (3, 3) and (1/3, 1/3) have products 9 and 1/9 and supplies 2 and 2/3; (4, 1), (1, 4)
# and (2, 2) all have product 4 and supplies 23/17, 23/17 and 3/2; at balance supply = AND(pro, con)
# + AND(ref), the arm current plus a constant (el-atlas 1350 is a structural correspondence, 1364)
assert bridge(F(3), F(3), *ref, F(1))[3] == 0 and bridge(F(1, 3), F(1, 3), *ref, F(1))[3] == 0
sup = lambda p, c: bridge(p, c, *ref, F(1))[2]
assert (sup(F(3), F(3)), sup(F(1, 3), F(1, 3))) == (F(2), F(2, 3))
assert F(3) * F(3) == 9 and F(1, 3) * F(1, 3) == F(1, 9)
assert sup(F(4), F(1)) == sup(F(1), F(4)) == F(23, 17) and sup(F(2), F(2)) == F(3, 2)
assert F(4) * F(1) == F(1) * F(4) == F(2) * F(2) and sup(F(4), F(1)) != sup(F(2), F(2))  # not a function of mass
assert sup(F(3), F(3)) == AND(F(3), F(3)) + AND(*ref) and sup(F(2), F(2)) == AND(F(2), F(2)) + AND(*ref)
assert bridge(F(3), F(1), *ref, F(1))[3] != 0  # off the reference ratio: the detector reads the bias
arm = lambda p, c: p * (1 - bridge(p, c, *ref, F(1))[0])  # v7's "mass": the current in the card's own arm
assert (arm(F(4), F(1)), arm(F(1), F(4)), arm(F(2), F(2))) == (F(16, 17), F(13, 17), F(1))  # bias-dependent
assert arm(F(3), F(3)) == AND(F(3), F(3)) and arm(F(1, 3), F(1, 3)) == AND(F(1, 3), F(1, 3))  # at balance
det = lambda p, c: bridge(p, c, *ref, F(1))[3]
assert det(F(4), F(1)) > 0 > det(F(1), F(4))  # the sign of the detector is the sign of the bias
assert F(4) / F(1) == F(8) / F(2) and det(F(4), F(1)) != det(F(8), F(2))  # off null its size mixes bias and scale
# so the bias is read as the exact ratio pro/con against the reference ratio (the bridge supplies the
# null test and the sign), and the mass is the product, read directly
rails = [F(n, d) for n in range(1, 8) for d in range(1, 8)]  # each rail normalised by its own queue median
for pn, cn in product(sorted(set(rails)), repeat=2):
    mass, bias = pn * cn, pn / cn
    both = pn > 1 and cn > 1  # wanted and costly
    assert both == (mass > bias and mass > 1 / bias)  # bias here is the RATIO pn/cn: log m > |log(pn/cn)|, exact
    neither = pn < 1 and cn < 1
    assert neither == (mass < bias and mass < 1 / bias)
    if pn == 1 or cn == 1:  # a rail exactly at its median lies in no open quadrant: no flag
        assert not both and not neither

# ---- velocity as a conductance leaves currents unchanged; a gain per accelerator reorders the ranked value ----
def chain_current(i, v):
    phi = potentials({("s", "m"): v, ("m", "g"): v}, {"g"}, {"s": i})
    return v * (phi["m"] - phi["g"])


assert chain_current(F(3), F(1)) == chain_current(F(3), F(3)) == 3  # velocity on a chain: same current
assert COST["C"] * need("C") / COST["C"] == need("C")  # work removed per unit cost is W_c, the UNSPLIT demand (not the flow's)
# an accelerator of a card holding flow 1 (output reading; its gain multiplies its flow BEFORE the cost
# division: the stated reading, not a result, since a velocity gain and a card's own cost are different
# quantities and how they compose is open)
two = lambda g, cost_: value(g * F(1), cost_, u0)
assert two(F(2), F(2)) > two(F(3, 2), F(2)) and two(F(3, 2), F(1)) > two(F(2), F(2))  # gain per class reorders
# output against increment: the threshold on the accelerator's cost against the card it speeds
cy, eps = F(2), F(1001, 1000)
out_ahead = lambda cx, g: value(g, cx, u0) >= value(F(1), cy, u0)
inc_ahead = lambda cx, g: value(g - 1, cx, u0) >= value(F(1), cy, u0)
assert out_ahead(cy, eps) and not inc_ahead(cy, eps)  # a near-no-op: output still leads, increment does not
assert inc_ahead(cy * (G - 1), G) and not inc_ahead(cy * (G - 1) + 1, G)
assert out_ahead(cy * G, G) and not out_ahead(cy * G + 1, G)
# with EQUAL cost on every card (a cost-less one taken at u0) the order is today's salience order
assert sorted((F(1), F(11, 10), F(1, 2)), key=lambda p: -value(p, F(3), F(3))) == [F(11, 10), F(1), F(1, 2)]
# the behaviour change with unequal costs: today E1 (11/10) leads E2 (1); at costs 10 and 1, E2 leads
assert value(F(11, 10), F(1), u0) > value(F(1), F(1), u0)
assert value(F(11, 10), F(10), u0) < value(F(1), F(1), u0)
# ---- v11 (github:W146, Q1): the value is the delivery cost SAVED; several accelerators on one card compose
# multiplicatively, so the joint saving is not the sum of the separate savings ----
v11_saved = lambda gain, cost_: (1 - 1 / gain) * cost_
v11_c = F(8)
v11_joint = lambda gains, cost_: (1 - 1 / prod(gains)) * cost_
assert v11_saved(F(2), v11_c) == F(4)  # one gain of 2 saves half the cost
assert v11_joint([F(2), F(2)], v11_c) == F(6)  # two gains of 2 save 3/4 of the cost, not all of it
assert v11_saved(F(2), v11_c) + v11_saved(F(2), v11_c) == v11_c  # the SUM of the separate savings is the whole cost
assert v11_joint([F(2), F(2)], v11_c) != v11_saved(F(2), v11_c) + v11_saved(F(2), v11_c)  # ... which the joint saving is not
assert 0 < v11_saved(F(1001, 1000), v11_c) < F(1, 100)  # a near-no-op (G = 1.001) saves almost nothing, not the full flow
assert all(0 < v11_saved(g, v11_c) < v11_c for g in (F(11, 10), F(2), F(100)))  # positive rationals: no 0 and no infinity

# ---- v11 (github:W146, Q3): a cost-less card is EXCLUDED from the value ranking and routed to grooming ----
def v11_rank(cards, u0):
    costed = {n: pc for n, pc in cards.items() if pc[1] is not None}
    groom = sorted(n for n, pc in cards.items() if pc[1] is None)
    return sorted(costed, key=lambda n: -(costed[n][0] * u0 / costed[n][1])), groom


v11_base = {"V": (F(3, 2), F(4)), "W": (F(1), F(1)), "X": (F(1, 2), F(2)), "Z": (F(1, 4), F(2))}
v11_r0, v11_g0 = v11_rank(v11_base, F(1))
assert v11_g0 == [] and v11_r0 == ["W", "V", "X", "Z"]
v11_r1, v11_g1 = v11_rank({**v11_base, "U": (F(1), None)}, F(1))
assert v11_r1 == v11_r0 and v11_g1 == ["U"]  # a cost-less arrival moves no costed card and goes to grooming
assert v11_rank({**v11_base, "U": (F(1), None)}, F(5))[0] == v11_r0  # re-calibrating u0 cannot move a card

# ---- v11 (github:W146, Q6): decomposition follows an ABSOLUTE rule (one tick), never a cut at the median ----
v11_limit = F(3)  # a card that cannot finish in one tick: the loop-prompt rule, a constant, not a queue statistic
v11_atomize = lambda cards: sorted((n for n, pc in cards.items() if pc[1] is not None and pc[1] > v11_limit), key=lambda n: -cards[n][0])
v11_above_median = lambda cards: sorted(n for n, pc in cards.items() if pc[1] is not None and pc[1] > sorted(c for _, c in cards.values() if c is not None)[len([1 for _, c in cards.values() if c is not None]) // 2])
v11_cheap = {**v11_base, "Y1": (F(1), F(1)), "Y2": (F(1), F(1)), "Y3": (F(1), F(1))}  # three cheap arrivals move the median
assert v11_atomize(v11_base) == v11_atomize(v11_cheap) == ["V"]  # the absolute rule does not move with them
assert v11_above_median(v11_base) != v11_above_median(v11_cheap)  # the v10 median cut did, and flagged a fixed fraction

# ---- v11 (github:W146, Q2): the exchange argument under the objective (the sum of demand x completion time);
# X first iff c_X < (1 - 1/G) c_y + (w_X / w_y) c_y, so the ruling's threshold is exact only for a PURE accelerator ----
def v11_exchange(w_x, c_x, w_y, c_y, gain):
    x_first = w_x * c_x + w_y * (c_x + c_y / gain)
    y_first = w_y * c_y + w_x * (c_y + c_x)
    return x_first, y_first  # the smaller total is the better order


v11_wy, v11_cy, v11_g = F(2), F(6), F(3)  # y: demand 2, cost 6; the accelerator has gain 3
v11_pure = (1 - 1 / v11_g) * v11_cy  # the ruling's threshold, 4
assert v11_pure == F(4)
for cx_, want in ((F(3), "x"), (F(5), "y"), (F(4), "tie")):  # a PURE accelerator (no demand of its own)
    xf, yf = v11_exchange(F(0), cx_, v11_wy, v11_cy, v11_g)
    assert ("x" if xf < yf else "y" if yf < xf else "tie") == want
xf, yf = v11_exchange(F(1), F(5), v11_wy, v11_cy, v11_g)  # demand of its own: past the pure threshold, X still leads
assert F(5) > v11_pure and xf < yf
assert v11_pure + F(1) / v11_wy * v11_cy == F(7)  # the general threshold, 4 + (1/2) * 6
xf, yf = v11_exchange(F(1), F(7), v11_wy, v11_cy, v11_g)
assert xf == yf  # a tie at the general threshold

# ---- v11 (github:W146, Q5): k = 1 is Smith's rule, a NAMED external choice; v10's pair at k = 1 and k = 2 ----
def v11_weighted_completion(order):
    elapsed, total = F(0), F(0)
    for demand_, cost_ in order:
        elapsed += cost_
        total += demand_ * elapsed
    return total


v11_pair = [(F(4), F(2)), (F(3, 2), F(1))]  # (demand, cost) as in v10's pair
v11_by_k = lambda k: sorted(v11_pair, key=lambda dc: -dc[0] / dc[1] ** k)
assert v11_weighted_completion(v11_by_k(1)) == F(25, 2)  # 12.5: demand per unit cost first
assert v11_weighted_completion(v11_by_k(2)) == F(27, 2)  # 13.5: the k = 2 order is dearer on this pair
print("checks: every assertion held")
```
