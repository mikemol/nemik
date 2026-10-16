#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
#
# nemik:W590: the single-flight runner for tools/image_replica.sh. One replay costs about 16 minutes
# (nemik:W588), and commits arrive faster, so the runner holds a lock: a second start exits at once
# (the running loop picks up the newer sha when it finishes), and a burst of commits is replayed as
# the newest one, never one build per commit. Each result is one line in `.git/image-replica.last`:
#   <sha> <exit status> <seconds>
# which the tick reads (nemik:W592); this process never writes the queue. Each replay keeps its own
# log, `.git/image-replica-<first 7 of the sha>.log`, so a failure survives the next replay.
#   image_replica_runner.sh [REPLICA [REF]]
#   REPLICA  the replay script (default: tools/image_replica.sh beside the repo root)
#   REF      the ref to replay (default: origin/main, what the forge builds)
set -uo pipefail

repo="$(git rev-parse --show-toplevel)"
gitdir="$(git -C "$repo" rev-parse --absolute-git-dir)"
replica="${1:-$repo/tools/image_replica.sh}"
ref="${2:-origin/main}"
last="$gitdir/image-replica.last"

exec 9>"$gitdir/image-replica.lock"
flock -n 9 || exit 0

while :; do
	sha="$(git -C "$repo" rev-parse "$ref")" || exit 2
	if [ "$(cut -d' ' -f1 "$last" 2>/dev/null)" = "$sha" ]; then
		exit 0
	fi
	start="$(date +%s)"
	"$replica" "$sha" >"$gitdir/image-replica-${sha:0:7}.log" 2>&1
	status=$?
	printf '%s %s %s\n' "$sha" "$status" "$(($(date +%s) - start))" >"$last"
done
