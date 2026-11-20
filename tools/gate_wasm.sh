#!/bin/sh
# nemik:W2379: the gate's core.wasm check. src/nemik/web/core.wasm is built from Python by
# tools/build_wasm.sh and committed with its hash (nemik:W821, docs/wasm-pipeline.md); this rebuilds it
# from the staged tree and compares. Two things it does that the inline step in gate_staged.sh did not:
#
# 1. It names the pinned Codon the way MODULE.bazel does, by label: `bazel cquery --output=files
#    @codon//:bin/codon` answers the path, joined to `bazel info output_base` (the execution root's external/ is an empty directory). The inline step built
#    the path from a POSITION (+_repo_rules3+codon), which moves when a repo rule is added before codon in
#    MODULE.bazel; the path was then not executable and the step skipped itself.
# 2. It never skips. An input the step needs is not there (bazel does not name Codon, the path is not an
#    executable file, build_wasm.sh finds Codon or the host's llc or wasm-ld absent) means the check CANNOT
#    RUN: exit 7, the fleet's CANNOT_RUN, which the gate refuses on. A skip that exits 0 reports nothing
#    wrong while checking nothing (github-00's ruling on nemik:W2379). The honest cost is a host without
#    /usr/lib/llvm/23 cannot commit; nemik:W2381 pins llc and wasm-ld as bazel inputs so no host can lack them.
#
#   tools/gate_wasm.sh codon BAZEL...                print the pinned Codon's absolute path
#   tools/gate_wasm.sh run REAL_ROOT WT BAZEL...     rebuild WT's core.wasm with it and compare the hash
#
# BAZEL... is the bazel command as words (the gate passes its admission wrapper). Status: 0 the committed
# module is what the staged core builds; 1 it is not, or the build failed; 7 the check could not run. The
# module embeds the absolute path of Codon's stdlib, which has the output base's hash in it, and the gate's
# worktree has an output base of its own: so Codon is named from the REAL checkout, the one the committed
# module was built with.
set -eu
cannot_run=7

usage() {
    echo "usage: gate_wasm.sh codon BAZEL... | run REAL_ROOT WT BAZEL..." >&2
    exit 2
}

codon_path() {
    found=$("$@" cquery --output=files @codon//:bin/codon 2>/dev/null) || found=""
    if [ -z "$found" ]; then
        echo "gate_wasm: bazel did not name @codon//:bin/codon (the cquery failed or printed nothing)" >&2
        exit "$cannot_run"
    fi
    root=$("$@" info output_base 2>/dev/null) || root=""
    if [ -z "$root" ]; then
        echo "gate_wasm: bazel did not name its output base" >&2
        exit "$cannot_run"
    fi
    if [ ! -x "$root/$found" ]; then
        echo "gate_wasm: the pinned Codon $root/$found is not an executable file" >&2
        exit "$cannot_run"
    fi
    printf '%s\n' "$root/$found"
}

run() {
    real_root=$1
    wt=$2
    shift 2
    codon=$(cd "$real_root" && codon_path "$@")
    status=0
    out=$(CODON="$codon" sh "$wt/tools/build_wasm.sh" "$wt/.core.wasm" 2>&1) || status=$?
    if [ "$status" -eq "$cannot_run" ]; then
        echo "gate_wasm: core.wasm was not rebuilt, a tool is not available: $out" >&2
        exit "$cannot_run"
    fi
    if [ "$status" -ne 0 ]; then
        printf '%s\n' "$out" | tail -n 30 >&2
        echo "gate_wasm: tools/build_wasm.sh failed ($status)" >&2
        exit 1
    fi
    built=$(sha256sum <"$wt/.core.wasm" | cut -d' ' -f1)
    want=$(cut -d' ' -f1 "$wt/src/nemik/web/core.wasm.sha256")
    if [ "$built" != "$want" ]; then
        echo "gate_wasm: src/nemik/web/core.wasm is not what src/nemik/core builds (rebuild it with tools/build_wasm.sh and commit it with its hash)" >&2
        exit 1
    fi
}

case "${1:-}" in
codon)
    shift
    codon_path "$@"
    ;;
run)
    shift
    [ "$#" -ge 3 ] || usage
    run "$@"
    ;;
*) usage ;;
esac
