#!/usr/bin/env bash
# nemik:W2365: the pre-submit IS the commit gate, run over a review worktree's index, so what the gate
# refuses shows before a submit. W2357 v2 passed //:precommit and review and was refused at the gate by
# tools/rebaselines_gate.py, one of the gate's steps that //:precommit does not hold. gate_staged.sh
# gates whatever index GIT_INDEX_FILE names, and a linked worktree's index lives in this repository, so
# the tree gated here is the review worktree's staged tree, judged by the same script the commit hook
# runs: parity by construction, no second list of steps to drift.
#
#   tools/presubmit.sh WORKTREE     run from the real checkout; stdout: tree <sha> rc <status>
#
# A review message cites the printed tree, which must equal the review ref's tree. WORKTREE is refused
# when it is not a worktree of this repository, or holds anything unstaged or untracked: the gate would
# then judge a tree other than the one under review.
set -o pipefail

wt="${1:-}"
if [ -z "$wt" ]; then
    echo "usage: tools/presubmit.sh WORKTREE" >&2
    exit 2
fi
real_root="$(git rev-parse --show-toplevel)" || exit 1
ours="$(git -C "$real_root" rev-parse --path-format=absolute --git-common-dir)" || exit 1
theirs="$(git -C "$wt" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || theirs=""
if [ "$theirs" != "$ours" ]; then
    echo "presubmit: $wt is not a worktree of $real_root: refused" >&2
    exit 1
fi
if ! git -C "$wt" diff --quiet; then
    echo "presubmit: $wt has unstaged changes (the gate judges the index; stage them first): refused" >&2
    exit 1
fi
untracked="$(git -C "$wt" ls-files --others --exclude-standard)" || exit 1
if [ -n "$untracked" ]; then
    printf '%s\n' "$untracked" >&2
    echo "presubmit: $wt has untracked files (the gate judges the index; stage them first): refused" >&2
    exit 1
fi
idx="$(git -C "$wt" rev-parse --path-format=absolute --git-path index)" || exit 1
tree="$(GIT_INDEX_FILE="$idx" git -C "$real_root" write-tree)" || exit 1
echo "presubmit: gating tree $tree from $wt" >&2

rc=0
GIT_INDEX_FILE="$idx" MIKEMOL_REAL_ROOT="$real_root" "$real_root/tools/gate_staged.sh" || rc=$?
echo "tree $tree rc $rc"
exit "$rc"
