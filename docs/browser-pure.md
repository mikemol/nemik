# What runs over plain Card data today (nemik:W508)

**Status: an inventory, read from imports only; `rank`, `blocks` and the frontier walker measured
2026-10-18.** The goal: every computation the view needs
runs over plain `Card` data, so it can run in the browser (through mtools' web-subset gate, W1070,
and the TypeScript step, W1071). A module whose imports are only `nemik.cards` and the standard
library is a candidate as it stands; a module that imports `rdflib` or `nemik.adapter` reads the
graph and has to be ported first, keeping the graph version as the test reference (as W453 and
W454 did).

What this table is not: it reads module-level imports with grep, so a function-local import is
missed and a module that imports `rdflib` only for a type is listed as graph-reading. Each row
needs a read of its functions before its port is carded.

| Module | Imports (nemik and rdflib) | Reading | Next |
| --- | --- | --- | --- |
| `projection.py` (W425) | `nemik.cards` | Card-pure | candidate as it stands: run it through the web-subset gate |
| `flow.py` | none | pure; uses `Fraction`, which the TypeScript step needs a BigInt answer for (mtools:W1074) | wait on W1074, or give the solve an integer form |
| `health.py` (W454) | `rdflib.Graph`, `nemik.blocks.operator_asks`, `nemik.cards` | the Card part is pure; `operator_asks` reads the graph | split the Card-pure health from the operator-ask input |
| `critical.py` (W453) | `rdflib`, `nemik.adapter`, `nemik.blocks`, `nemik.cards`, `nemik.rank` | graph-reading (edges, namespaces) | port the edge walk to Card edges, keep the graph version as the reference |
| `salience.py` | `nemik.adapter`, `nemik.flow`, `nemik.rank` | graph-reading (`audit`) | port after `rank` |
| `rank.py` | module level: `re`, `tomllib`, `dataclasses`, `importlib.resources`, `rdflib` (`Graph`, `Literal`, `URIRef`, `DCTERMS`, `Node`), `nemik.tiers`, `nemik.adapter`; inside functions: `nemik.score`, `nemik.index`, `nemik.salience`, `nemik.critical`, `nemik.residue`, `nemik.check`, `mikemol.frontier.walk`, `fractions` | graph-reading (walks successors over an rdflib `Graph`), reads `rank-weights.toml` through `importlib.resources`, and its command line imports `nemik.check` | port the successor walk and weights to Card edges first; `salience` and `critical` follow it; the command line stays server-side |
| `blocks.py` (`annotate`) | module level: `re`, `typing.Any`, `rdflib` (`RDF`, `Graph`, `Literal`, `URIRef`, `DCTERMS`, `PROV`, `Node`), `nemik.adapter` | graph-reading: `annotate` writes derived triples (operator asks, ready-behind-open, cycles) into the graph | port the derivations as functions of Card edges that return flags, keeping `annotate` as the graph reference |
| frontier (shared walker, W483) | not in `src/nemik`: `rank.py` imports `mikemol.frontier.walk` (the mtools `frontier` distribution) inside a function | a shared package, outside nemik's tree | the web-subset gate for nemik cannot check it; ask mtools whether the walker is in the subset (mtools:W1070) |

## Next

One child card per row that needs a port, each with its manifest and the old graph version kept as
the test reference. The first two (`projection`, `flow`) need no port, only the gate run once mtools'
web-subset step is available to nemik.
