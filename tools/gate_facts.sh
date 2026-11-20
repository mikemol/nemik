#!/bin/sh
# nemik:W2344: the git facts the gate's cached bazel tests judge. The operator's ruling (host
# transcript 695f3e0a line 190734) is that checks work WITH bazel's cache, so each check is its own
# hermetic test target (tools/hook_facts.py holds the judgments). A bazel test cannot run git, so git's
# answers are collected here as DATA, and each test declares the file it reads as an input.
#
# The facts come from the STAGED TREE object the gate is about to test (ls-tree and diff-tree on the
# tree's sha), never from the live checkout. Each file's first line names its KIND, so a text handed to
# the wrong parser is refused (nemik:W2350), and then stamps the tree it describes and the HEAD the
# gate commits on. changed.txt is a function of both (it is diffed against HEAD); tracked.txt is a
# function of the tree alone, but carries the HEAD too (nemik:W2345, the no-maybe-results ruling: every
# verdict is stamped with both, so none is a result that may or may not carry a head):
#
#   facts tracked          (tracked.txt, its first line)   facts changed   (changed.txt)
#   tree <sha>             (both files, the second line)
#   head <sha>             (both files, the third line)
#
# the tests refuse facts stamped for another tree or HEAD, so a stale file cannot silently lie. In the
# gate a stale file cannot survive anyway: tools/gate_staged.sh cleans the worktree (git clean -fdx,
# under its lock) before it calls this. --check is for a hand run.
#
#   tools/gate_facts.sh WORKTREE TREE HEAD          write WORKTREE/.gate-facts/tracked.txt and changed.txt
#   tools/gate_facts.sh --check WORKTREE TREE HEAD  exit 1 unless the files on disk are what git says now
#
# tracked.txt: the paths of the tree under src/nemik, tests and vendor/wheels (the named-inputs and
# wheel checks read it). changed.txt: the paths that differ between HEAD and the tree (the working-card
# rule reads it). Each is written whole to a temporary file and moved into place.
set -eu
mode="write"
if [ "${1:-}" = "--check" ]; then
	mode="check"
	shift
fi
if [ "$#" -ne 3 ]; then
	echo "usage: gate_facts.sh [--check] WORKTREE TREE HEAD" >&2
	exit 2
fi
wt=$1
tree=$2
head=$3
dir="$wt/.gate-facts"

emit() {
	case "$1" in
	tracked)
		printf 'facts tracked\ntree %s\nhead %s\n' "$tree" "$head"
		git -C "$wt" ls-tree -r --name-only "$tree" -- src/nemik tests vendor/wheels
		;;
	changed)
		printf 'facts changed\ntree %s\nhead %s\n' "$tree" "$head"
		git -C "$wt" diff-tree -r --name-only --no-commit-id "$head" "$tree"
		;;
	*)
		echo "gate_facts: no such fact: $1" >&2
		return 2
		;;
	esac
}

for name in tracked changed; do
	target="$dir/$name.txt"
	if [ "$mode" = "check" ]; then
		tmp=$(mktemp "${TMPDIR:-/tmp}/gate-facts.XXXXXX")
		emit "$name" >"$tmp"
		if ! cmp -s "$tmp" "$target"; then
			rm -f "$tmp"
			echo "gate_facts: $target is missing or is not what git says for tree $tree" >&2
			exit 1
		fi
		rm -f "$tmp"
	else
		mkdir -p "$dir"
		tmp=$(mktemp "$dir/$name.XXXXXX")
		emit "$name" >"$tmp"
		mv "$tmp" "$target"
	fi
done
# nemik:W2345: the directory is handed to bazel as a repository (--inject_repository=gate_facts=), which
# needs a package and a repo marker; the two facts files are the only labels it exports.
if [ "$mode" = "write" ]; then
	printf 'exports_files(["tracked.txt", "changed.txt"])\n' >"$dir/BUILD.bazel"
	: >"$dir/REPO.bazel"
fi
