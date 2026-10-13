# Vendored wheels

`mikemol_pathsforward-0.1.0+<sha>-py3-none-any.whl` (uv.lock pins it; its hash is in SHA256SUMS) is
built from mtools' pathsforward at the exact commit nemik pins (the local version segment names it,
since mtools does not bump its own version per commit), via:

    git -C ~/github/mtools archive <sha> -- pathsforward \
      | tar -x -C <tmp> && cd <tmp>/pathsforward && uv build --wheel -o <out>

This is nemik:H1 (nemik:W6): the image build no longer fetches from github.com at build time. To
bump the pin, rebuild the wheel the same way at the new commit, name it
`mikemol_pathsforward-0.1.0+<short-sha>-py3-none-any.whl`, `git rm` the old one, and update
pyproject.toml's `tool.uv.sources` path to match.

History: 9236d5e (nemik:W6, superseded) -> 8a279a1 (nemik:W10: --enables clear, mtools:W40) ->
3cb24fb (nemik:W10: --init, mtools:W42) -> 33005c1 (nemik:W10: --ledger accepts `-` as
the queue-level symbol, since argparse eats a bare -- itself; mtools:W43) -> 8c24617
(nemik:W20: model.leverage()/describe_rank() added; ordered() sorts by (status, -leverage,
file order); render.queue() falls back to describe_rank when rank_reason is unset;
mtools:W51) -> e4f478b (nemik:W40: ATOMIZE W<n> (top for k ticks) in --check/--check-evidence/--payload when the top workable waypoint was advanced by a prior tick; mtools:W111/W113) -> c713252 (nemik:W43: stored integer `weight`, --update --weight N; ordered() sorts (status, -weight, -leverage, file order); missing weight = 0; mtools:W115) -> f945d43 (nemik:W44: --update stamps last_worked only for work fields (status/blocked-on/blocked-kind/next/evidence-append); --weight/--title/--enables/--ticks-blocked are metadata; mtools:W117) -> d491475 (nemik:W48: --weights-from FILE.json, all-or-nothing bulk weights under one lock; mtools:W116) -> 836f20e (nemik:W50: --update --touches replaces touches[] as metadata; mtools:W122) -> 49ac0ff (nemik:W52: --overlaps prints OVERLAP <tag>: W<a>,W<b> over ready/working; mtools:W118) -> 6f81801 (nemik:W55: --bump-blocked prunes done local blockers, empty list returns to ready; mtools:W125) -> 4de0da4 (nemik:W64: waypoint `witness` field, --add/--update --witness QUERY, stored verbatim, never run; mtools:W131) -> 8d9ea4e (nemik:W59: --check flags a witnessed waypoint that is ready or working; mtools:W132) -> 345c06c (nemik:W67: witnessed waypoints are never workable: ordered(), payload step and ATOMIZE skip them; mtools:W133) -> 23f1223 (nemik:W130: waypoint `vector` + `vector_source` fields, WV:1 grammar in vector.py, --check validates stored vectors and prints UNSCORED <n>; mtools:W248/W256/W257) -> a2b7b62 (nemik:W136: --update SYMBOL --caused-by REF, one-token-checked as --add, empty clears, metadata; mtools:W305) -> 765c1f4 (nemik:W129: dtstart/due (mtools:W300) and alarms (mtools:W279), timevalue.parse/parse_trigger; mtools:W299/W300/W279) -> f22d7fe (nemik:W146: timevalue.fires_at/duration resolve alarms; --alarm -PT1H accepted; mtools:W307/W308) -> 03749d5 (operator 2026-10-04: one sha for all three vendored mtools wheels; adds --inbound, --prune-landed, embargoes, ledger outcome sets, six of nemik's shapes in --check) -> 472f940 (nemik:W230: one sha again; ships the Rego realizability policy as package data, `--certify`, and the realizability fields in the queue; mtools:W850) -> d14270f (nemik:W257: `--admit` on `--add`/`--update`/`--drop` and the marks ledger `<queue>.marks.jsonl`, `--certify --facts`, the waypoint fields reference_arm, command, population and deferred; mtools:W851/W852/W854/W849) -> c4d4b56 (nemik:W276: waypoint `attachments` [{path, sha256}] and `--update --attach PATH`, mtools:W930/W931; re-vendored with tools/revendor-mtools.sh) -> 842ab10 (nemik:W281: --check reports an attachment whose file is missing, not a plain file, or whose sha256 changed; mtools:W932) -> 7d4a458 (nemik:W304: nemik-pins reported 41 commits behind; includes pycodemod judged-fix and later mtools changes) -> f04f0a2 (nemik:W377: the fleet par from luthen's repin_par.txt; mikemol-commit prints its path and lock, mtools:W1015, with the fence fallback, W1016/W1022) -> 2eeb11e (nemik:W417: adds mikemol-rulerseq, mtools:W1048, the ruler-sequence generator nemik-serve computes patterns with) -> bf2b8e8 (nemik:W444: mikemol-commit's identity check, RACED instead of reporting another committer's commit, mtools:W1107, and its stale-index refresh, mtools:W1108; ahead of the fleet par f04f0a2, which predates both) -> 7adcefb (nemik:W447: mikemol-paths-forward --tick-open and --tick-close, mtools:W1078/W1079, one verb each to open and end a tick) -> c47d50b (nemik:W457: --tick-close prunes landed local blockers before its check and prints each card it frees, mtools:W1112) -> 3ded8d1 (nemik:W476: --block-behind-open [--write] blocks a ready card behind its open local enabler, mtools:W1131).

`mikemol_icsstruct-0.1.0+<sha>-py3-none-any.whl` (nemik:W157) is mtools' icsstruct at the same sha,
built the same way (`git archive <sha> -- icsstruct`, `uv build --wheel`). It supplies `mikemol-ics`,
which reads the operator calendars the Akonadi helper exports (W147) for W113.

`mikemol_rulerseq-0.1.0+<sha>-py3-none-any.whl` (nemik:W417) is mtools' rulerseq at the same sha:
`mikemol.rulerseq`, paperkit's ruler-sequence generator hosted by mtools (mtools:W1048). Stdlib only.

`mikemol_hooks-0.1.0+<sha>-py3-none-any.whl` is mtools' hooks distribution at the same sha
(`git archive <sha> -- hooks`, `uv build --wheel`). nemik wires two of its console scripts,
`mikemol-hook-inbound-asks` and `mikemol-hook-nemik-check`, in `.claude/settings.json`. It brings
`ruff` and `mypy` into the lock (the distribution's own dependencies). All three mtools wheels move
together, to one sha, per mtools INSTALL.md.

## Hashes

`SHA256SUMS` beside the wheels, written by `tools/revendor-mtools.sh` on every bump (nemik:W417:
the hand-kept list here went stale with each bump); `sha256sum -c SHA256SUMS` in this directory
verifies them, and uv.lock pins the same digests. mikemol_fence is mtools' fence (nemik:W378), for
`mikemol-membudget`, the commit lock mikemol-commit takes.
