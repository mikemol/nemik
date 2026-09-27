# Vendored wheels

`mikemol_pathsforward-0.1.0+c713252-py3-none-any.whl` is built from mtools' pathsforward at the
exact commit nemik pins (`c713252`; local version segment names it, since mtools does not bump its
own version per commit), via:

    git -C ~/github/mtools archive c713252 -- pathsforward \
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
mtools:W51) -> e4f478b (nemik:W40: ATOMIZE W<n> (top for k ticks) in --check/--check-evidence/--payload when the top workable waypoint was advanced by a prior tick; mtools:W111/W113) -> c713252 (nemik:W43: stored integer `weight`, --update --weight N; ordered() sorts (status, -weight, -leverage, file order); missing weight = 0; mtools:W115).
