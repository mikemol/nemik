# Vendored wheels

`mikemol_pathsforward-0.1.0+8d9ea4e-py3-none-any.whl` is built from mtools' pathsforward at the
exact commit nemik pins (`8d9ea4e`; local version segment names it, since mtools does not bump its
own version per commit), via:

    git -C ~/github/mtools archive 8d9ea4e -- pathsforward \
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
mtools:W51) -> e4f478b (nemik:W40: ATOMIZE W<n> (top for k ticks) in --check/--check-evidence/--payload when the top workable waypoint was advanced by a prior tick; mtools:W111/W113) -> c713252 (nemik:W43: stored integer `weight`, --update --weight N; ordered() sorts (status, -weight, -leverage, file order); missing weight = 0; mtools:W115) -> f945d43 (nemik:W44: --update stamps last_worked only for work fields (status/blocked-on/blocked-kind/next/evidence-append); --weight/--title/--enables/--ticks-blocked are metadata; mtools:W117) -> d491475 (nemik:W48: --weights-from FILE.json, all-or-nothing bulk weights under one lock; mtools:W116) -> 836f20e (nemik:W50: --update --touches replaces touches[] as metadata; mtools:W122) -> 49ac0ff (nemik:W52: --overlaps prints OVERLAP <tag>: W<a>,W<b> over ready/working; mtools:W118) -> 6f81801 (nemik:W55: --bump-blocked prunes done local blockers, empty list returns to ready; mtools:W125) -> 4de0da4 (nemik:W64: waypoint `witness` field, --add/--update --witness QUERY, stored verbatim, never run; mtools:W131) -> 8d9ea4e (nemik:W59: --check flags a witnessed waypoint that is ready or working; mtools:W132).
