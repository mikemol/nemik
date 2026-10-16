#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
#
# nemik:W590: the single-flight runner for tools/image_replica.sh. One replay costs about 16 minutes
# (nemik:W588), and commits arrive faster, so the runner holds a lock: a second start exits at once
# (the running loop picks up the newer sha when it finishes), and a burst of commits is replayed as
# the newest one, never one build per commit. Each result is one line in `.git/image-replica.last`:
#   <sha> <exit status> <seconds>
# which the tick reads (nemik:W592); this process never writes the queue.
#
# nemik:W596 (operator 2026-10-16: "you log to services, not to files"): the replay's output lines go
# to the fleet log service through a SHIPPER, a command that reads lines on stdin. The shipper is
# luthen's OTLP log producer (luthen-observability:W1157, 551d9649: service.name=nemik.image-replica,
# the sha as a field, read back from VictoriaLogs before it exits 0); it is the default when luthen's
# venv exists on the host, and the lines reach it by a pipe (it reads /dev/stdin).
# `.git/image-replica-<sha7>.log` is only a cache of the same lines, never the evidence.
#   image_replica_runner.sh [REPLICA [REF [SHIPPER]]]
#   REPLICA  the replay script (default: tools/image_replica.sh beside the repo root)
#   REF      the ref to replay (default: origin/main, what the forge builds)
#   SHIPPER  the stdin-lines command, `{sha}` replaced by the 7-character sha; `none`: the cache
#            file only; absent: luthen's OTLP log producer when its venv exists, else none
set -uo pipefail

repo="$(git rev-parse --show-toplevel)"
gitdir="$(git -C "$repo" rev-parse --absolute-git-dir)"
replica="${1:-$repo/tools/image_replica.sh}"
ref="${2:-origin/main}"
shipper="${3:-default}"
otlp_dir=/home/mikemol/github/luthen-observability
if [ "$shipper" = "default" ]; then
	if [ -x "$otlp_dir/.venv/bin/python" ]; then
		shipper="env -C $otlp_dir .venv/bin/python -m checks.otlp_log --service nemik.image-replica --namespace nemik --field sha={sha}"
	else
		shipper=none
	fi
fi
last="$gitdir/image-replica.last"

exec 9>"$gitdir/image-replica.lock"
flock -n 9 || exit 0

while :; do
	sha="$(git -C "$repo" rev-parse "$ref")" || exit 2
	if [ "$(cut -d' ' -f1 "$last" 2>/dev/null)" = "$sha" ]; then
		exit 0
	fi
	start="$(date +%s)"
	cache="$gitdir/image-replica-${sha:0:7}.log"
	if [ "$shipper" = "none" ]; then
		"$replica" "$sha" >"$cache" 2>&1
		status=$?
	else
		read -r -a ship <<<"${shipper//\{sha\}/${sha:0:7}}"
		"$replica" "$sha" 2>&1 | tee "$cache" | "${ship[@]}" >/dev/null 2>&1
		status="${PIPESTATUS[0]}"
	fi
	printf '%s %s %s\n' "$sha" "$status" "$(($(date +%s) - start))" >"$last"
done
