#!/bin/sh
# nemik:W820: build src/nemik/web/chains.wasm from wasm/chains_entry.codon and src/nemik/core.
#
#   tools/build_wasm.sh [OUT]       OUT defaults to src/nemik/web/chains.wasm
#
# Codon compiles the entry to LLVM IR; llc turns the IR into a wasm64 object (memory64: Codon's IR
# carries 64-bit sizes, so wasm32 is not an option, docs/wasm-pipeline.md); wasm-ld links it with the
# runtime left to the page (wasm.js supplies seq_alloc and the rest). The pinned Codon is found in
# Bazel's external tree, or by $CODON; the LLVM tools by $LLVM_BIN (default /usr/lib/llvm/23/bin).
# Exits 3 with a reason when a tool is absent, so the gate can say why it did not rebuild.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$here/src/nemik/web/chains.wasm"}
llvm=${LLVM_BIN:-/usr/lib/llvm/23/bin}
codon=${CODON:-}
if [ -z "$codon" ]; then
	base=$(cd "$here" && bazel info output_base 2>/dev/null || true)
	codon="$base/external/+_repo_rules3+codon/bin/codon"
fi
for tool in "$codon" "$llvm/llc" "$llvm/wasm-ld"; do
	if [ ! -x "$tool" ]; then
		echo "build_wasm: $tool is not available" >&2
		exit 3
	fi
done
work=$(mktemp -d "${TMPDIR:-$HOME/scratch}/build_wasm.XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/nemik/core"
cp "$here"/src/nemik/core/*.py "$work/nemik/core/"
cp "$here/wasm/chains_entry.codon" "$work/chains_entry.codon"
(cd "$work" && "$codon" build --release -o chains_entry.ll chains_entry.codon)
# the IR names x86 CPU features llc ignores with one warning each; the result is what matters
"$llvm/llc" -mtriple=wasm64-unknown-unknown -mcpu=generic -filetype=obj \
	-o "$work/chains_entry.o" "$work/chains_entry.ll" 2>/dev/null
# the shadow stack is 8 MiB: the default 64 KiB overflows on a graph of a couple of thousand cards
"$llvm/wasm-ld" -mwasm64 --no-entry --export=chains --export=main --export=__heap_base --allow-undefined \
	--gc-sections --strip-all -z stack-size=8388608 -o "$out" "$work/chains_entry.o"
echo "build_wasm: $out"
