# Vendored wheels

`mikemol_pathsforward-0.1.0-py3-none-any.whl` is built from mtools' pathsforward at the exact
commit nemik pins (`9236d5e525dc074ef73a779ca55478e7ece3dd32`), via:

    git -C ~/github/mtools archive 9236d5e525dc074ef73a779ca55478e7ece3dd32 -- pathsforward \
      | tar -x -C <tmp> && cd <tmp>/pathsforward && uv build --wheel -o <out>

This is nemik:H1 (nemik:W6): the image build no longer fetches from github.com at build time. To
bump the pin, rebuild the wheel the same way at the new commit, replace this file, and update
pyproject.toml's `mikemol-pathsforward` path to match.
