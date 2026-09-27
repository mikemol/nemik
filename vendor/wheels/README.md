# Vendored wheels

`mikemol_pathsforward-0.1.0+33005c1-py3-none-any.whl` is built from mtools' pathsforward at the
exact commit nemik pins (`8a279a1`; local version segment names it, since mtools does not bump its
own version per commit), via:

    git -C ~/github/mtools archive 8a279a1 -- pathsforward \
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
mtools:W51).
