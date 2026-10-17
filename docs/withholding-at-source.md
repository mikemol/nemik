# Withholding at the source (nemik:W516)

**Status: design, nothing built.** Written for whoever builds the children W516 is split into.

## Today

luthen's withheld list (`withheld.json`, shape v1: `{"version": 1, "items": [{"ref": "repo:W<n>", ...}]}`)
is applied inside nemik's static build by `src/nemik/withheld.py`: fail closed (no file, no build),
withhold whole, never scrub, a stub carrying only the symbol where a published item points at a
withheld one. The pod therefore *sees* every card and relies on nemik to drop the withheld ones.

## The boundary this card moves

The operator's ruling: the pod should not see data that must not pass. So the decision of what may
leave a repo moves to that repo, and nemik and its pod can only read the product of that decision.

## Design

1. **A repo's export is its own product.** Each repo's writer produces `export.json` of what may
   leave it, by that repo's policy. Shape v2:
   `{"version": 2, "repo": "<name>", "as_of": "<RFC 3339>", "cards": [<publishable cards>],
   "withheld": ["<repo>:W<n>", ...]}`.
   - `cards` carries only publishable cards, whole. A withheld card is absent from it.
   - `withheld` carries refs only: enough for a stub where a published card points at one, so no
     dependency silently disappears (the v1 reading luthen confirmed on 2026-10-01).
2. **Fail closed, per repo.** A repo with no export, or an export that does not parse or has an
   unknown version, publishes nothing, and the build reports that repo as unpublished. Whether one
   repo's failure fails the whole build is an open question below.
3. **The pod mounts only exports.** `deploy/deployment.yaml` mounts the exports read-only and
   nothing else from a repo, which is what the README Hosting section already states as the intent.
4. **Migration is compatible first.** Step one: nemik derives a v2 export per repo from today's
   queue plus luthen's v1 list, so the reader side (`withheld.py` taking v2) can land and be tested
   before any repo changes. Step two: each repo's writer emits its own export and luthen's list
   shrinks to nothing. v1 keeps loading until the last repo has moved.

## Children

| Child | Edits | Closes on |
| --- | --- | --- |
| Reader: `withheld.py` and the static build take per-repo v2 exports, fail closed per repo | `src/nemik/withheld.py` and its tests | a test that a repo with no export publishes nothing |
| Compat producer: derive a v2 export per repo from queue plus the v1 list | new module under `src/nemik/` | the derived export applied equals today's v1 result on the fleet |
| Writer side: the paths-forward writer emits `export.json` by repo policy | mtools (ask) | mtools card, cited here |
| Pod mounts only exports | `deploy/deployment.yaml` | `tests/test_deploy_manifest.py` pins the mounts |
| Retire luthen's v1 list | luthen (ask) | no repo's cards depend on it |

## Open questions

- Does one repo's missing export fail the whole build, or publish the rest and flag the gap?
  Fail-closed per repo is the safe reading; the operator may want the whole-build reading.
- Where a repo's policy is not yet written, is its export empty (publish nothing) or derived from
  the v1 list (compat)? The migration above assumes the latter until the repo opts in.
