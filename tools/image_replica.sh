#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
#
# nemik:W589: replay the image's test stage (Containerfile, target `test`) on a fresh clone of one
# commit, so an image failure shows up in minutes instead of when the forge's build reaches it.
# Measured 2026-10-16 at 15 min 42 s, too slow for the per-commit gate (W588), so it runs after a
# push, in the background, and reports through the queue writer:
#   tools/image_replica.sh [SHA]    exit 0 = the stage passed; any other exit = it failed
# On failure the caller files `mikemol-paths-forward --gate-red`, on success `--gate-green`.
set -uo pipefail

repo="$(git rev-parse --show-toplevel)"
sha="$(git -C "$repo" rev-parse "${1:-HEAD}")"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

git clone --quiet "$repo" "$scratch/clone" || exit 2
git -C "$scratch/clone" checkout --quiet "$sha" || exit 2
printf 'image_replica: %s\n' "$sha"
buildctl build --frontend dockerfile.v0 \
	--local "context=$scratch/clone" --local "dockerfile=$scratch/clone" \
	--opt filename=Containerfile --opt target=test --progress=plain
exit $?
