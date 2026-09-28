#!/usr/bin/env bash
# nemik:W104 (W101c): arm a clone. Run once per clone; idempotent. mtools' setup.sh pattern.
#
# ⚑ THE HOST .venv IS THE BAZEL OUTPUT, NOT A uv SYNC. Operator 2026-09-27: "bazel builds the .venv
# to produce a .venv as a build output. That .venv is then a build input for everything subsequent
# that needs .venv material." So `.venv` is a link to bazel-bin/.venv, the same venv every test
# runs under (W103). Do not `uv sync` into it: it is a read-only build output. Rebuild with
# `bazel build //:.venv` after a source or lock change.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
cd "$root"

# A fresh clone's core.hooksPath is empty, so the pre-commit gate (W92) would never run.
git config core.hooksPath .githooks
echo "setup: core.hooksPath = $(git config --get core.hooksPath)"

bazel build //:.venv --noshow_progress
if [ -e .venv ] && [ ! -L .venv ]; then
    # A uv-synced venv from before W104: move it aside rather than delete it.
    mv .venv ".venv.uv-$(date +%s)"
    echo "setup: moved the old uv .venv aside"
fi
ln -sfn bazel-bin/.venv .venv
echo "setup: .venv -> $(readlink .venv)"
.venv/bin/python3 -c "import nemik, mikemol.pathsforward; print('setup: .venv imports nemik and pathsforward')"
