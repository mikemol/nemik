#!/bin/sh
# nemik: re-vendor the three mtools wheels (pathsforward, icsstruct, hooks) at ONE commit, the
# procedure of vendor/wheels/README.md ("To bump the pin") as a script, so a bump is one command.
#
#   tools/revendor-mtools.sh <new-sha> <old-sha> [path-to-mtools-clone]
#
# It builds each wheel from `git archive <new-sha>`, names it 0.1.0+<short-sha>, removes the old
# wheels, rewrites pyproject.toml and MODULE.bazel to the new names, runs `uv lock`, and prints the
# new hashes. It does not touch the README history or hash list, and it does not commit.
set -eu
new=$1
old=$2
mtools=${3:-"$HOME/github/mtools"}
here=$(cd "$(dirname "$0")/.." && pwd)
out="$here/vendor/wheels"
short=$(git -C "$mtools" rev-parse --short=7 "$new")
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

for dist in pathsforward icsstruct hooks; do
	git -C "$mtools" archive "$new" -- "$dist" | tar -x -C "$tmp"
	sed -i "s/^version = .*/version = \"0.1.0+$short\"/" "$tmp/$dist/pyproject.toml"
	(cd "$tmp/$dist" && uv build -q --wheel -o "$out")
done

for file in "$here/pyproject.toml" "$here/MODULE.bazel"; do
	sed -i "s/0\.1\.0+$old/0.1.0+$short/g; s/mtools $old/mtools $short/g" "$file"
done
git -C "$here" rm -q -f "$out"/*+"$old"-*.whl
# vendor/wheels/.gitignore is `*` (the wheels are tracked by force), so the new ones are added by -f.
git -C "$here" add -f "$out"/*+"$short"-*.whl
(cd "$here" && uv lock)
sha256sum "$out"/*+"$short"-*.whl
