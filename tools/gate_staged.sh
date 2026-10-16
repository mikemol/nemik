#!/usr/bin/env bash
# nemik:W374: run the gate over the STAGED tree (the index), never the working tree, in a persistent
# worktree at a FIXED path. bazel keys its output base (cache and server) on the workspace path, so a
# fixed path stays warm across commits; gating in a fresh snapshot each time would start a new bazel
# server with a cold cache per commit (the host-memory problem of 2026-10-12). Modelled on
# linux-sources' tools/gate_staged.sh.
#
# Under mikemol-commit's isolated run the hook's cwd is a snapshot (tracked files only, no .git), so
# MIKEMOL_REAL_ROOT names the real checkout and every git call goes through it. Unset, the real root
# is this checkout.
#
#   tools/gate_staged.sh        gate the index;  GATE_WT overrides the worktree path (tests)
set -o pipefail

real_root="${MIKEMOL_REAL_ROOT:-$(git rev-parse --show-toplevel)}" || exit 1
wt="${GATE_WT:-$(dirname "$real_root")/.nemik-gate-wt}"

# Under a hook git exports its repo env, GIT_INDEX_FILE relative to the checkout. That index is the
# one to gate (under `git commit <paths>` it is a temporary index), so capture it, then clear git's
# env so the worktree's calls see their own repository.
idx="${GIT_INDEX_FILE:-}"
if [ -n "$idx" ]; then
    case "$idx" in /*) ;; *) idx="$real_root/$idx" ;; esac
else
    idx="$(git -C "$real_root" rev-parse --git-path index)" || exit 1
    case "$idx" in /*) ;; *) idx="$real_root/$idx" ;; esac
fi
unset GIT_INDEX_FILE GIT_DIR GIT_WORK_TREE GIT_PREFIX GIT_OBJECT_DIRECTORY

# One gate at a time in the shared worktree.
exec 9>"$wt.lock" || exit 1
flock 9 || exit 1

if [ ! -e "$wt/.git" ]; then
    git -C "$real_root" worktree add --detach "$wt" HEAD >/dev/null || exit 1
fi
head_sha="$(git -C "$real_root" rev-parse HEAD)" || exit 1
git -C "$wt" checkout --quiet --detach --force "$head_sha" || exit 1
git -C "$wt" clean -fdxq -e 'bazel-*' -e .venv || exit 1
tree="$(GIT_INDEX_FILE="$idx" git -C "$real_root" write-tree)" || exit 1
git -C "$wt" read-tree --reset -u "$tree" || exit 1

cd "$wt" || exit 1
# The tree's .venv is a bazel output, never tracked, and some checks run it by path (paper.toml's
# `claim:` check is `.venv/bin/python3 checks/claims.py`): build it here as the checkout has it.
bazel build //:.venv --show_result=0 --noshow_progress || exit 1
ln -sfn bazel-bin/.venv .venv || exit 1
# nemik:W421: the registries a change must also update (a new command's SKILL.md row and workflows
# entry, a shape's SKILL.md row, an architecture claim's projection) fail in seconds here, before the
# whole suite: W365 and W400 each spent two ~10-minute gate rounds finding them one at a time.
fast=(//:test_skill //:test_workflows //:test_architecture)
if ! bazel test "${fast[@]}" --noshow_progress; then
    echo "gate_staged: a registry check FAILED (fast pass, before the full suite): commit refused" >&2
    exit 1
fi
# nemik:W571: the image's test stage runs plain pytest with none of Bazel's NEMIK_* variables and the
# project installed editable. Two commits passed the Bazel gate and failed there on 2026-10-16 (a test
# module read os.environ["NEMIK_CODON"] at import: collection error; mypy reached src/nemik/x.py by path
# and by import: "Source file found twice"). Replay both here in seconds, on the staged tree.
if ! out=$(env -i PATH="$PATH" HOME="$HOME" .venv/bin/python3 -m pytest --collect-only -q tests 2>&1); then
    printf '%s\n' "$out" | tail -n 30 >&2
    echo "gate_staged: a test module does not collect without Bazel's environment (the image's test stage would exit 2): commit refused" >&2
    exit 1
fi
if ! out=$(env PYTHONPATH="$wt/src" .venv/bin/python3 tools/mypy_ratchet.py 2>&1); then
    printf '%s\n' "$out" | tail -n 30 >&2
    echo "gate_staged: the mypy ratchet fails with the package importable from src (the image installs it editable): commit refused" >&2
    exit 1
fi
# nemik:W521: the gate is one bazel target, //:precommit (a test_suite over every test; the lint, type,
# shell and warrant stages join it as they land), so BuildBuddy captures its logs as one invocation.
if bazel test //:precommit --noshow_progress; then
    echo "gate_staged: green on the staged tree ($wt)" >&2
    exit 0
fi
echo "gate_staged: the gate FAILED on the staged tree ($wt): commit refused" >&2
exit 1
