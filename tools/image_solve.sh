#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
#
# nemik:W866: solve the Containerfile with the pinned BuildKit frontend, so an image build that cannot
# even be converted (nemik:W865: COPY --from took a variable, "failed to parse stage name", and no
# image shipped for hours) fails the commit and not the forge's build. It builds the `gated` path,
# which is the shared final stage and takes seconds; the `test` path differs only in which stage the
# final one takes its marker from, so a conversion error shows in either.
#   tools/image_solve.sh [DIR]   exit 0 = it solved; 1 = the solve failed; 7 = it cannot run (no
#                                buildctl, or no BuildKit daemon answering it), saying which
# nemik:W2382: 7 is the fleet's CANNOT_RUN, and the gate refuses on it like on 1. It was exit 3 and the
# gate said "not solved here" and went on: a skip that exits 0 reports nothing wrong while checking
# nothing (the same fail-open class as nemik:W2379's core.wasm step).
set -uo pipefail

dir="$(cd "${1:-.}" && pwd)" || exit 2
if ! command -v buildctl >/dev/null 2>&1; then
	printf 'image_solve: no buildctl on this host: the Containerfile cannot be solved\n'
	exit 7
fi
if ! buildctl debug workers >/dev/null 2>&1; then
	printf 'image_solve: no BuildKit daemon answers buildctl: the Containerfile cannot be solved\n'
	exit 7
fi
printf 'image_solve: %s\n' "$dir"
buildctl build --frontend dockerfile.v0 \
	--local "context=$dir" --local "dockerfile=$dir" \
	--opt filename=Containerfile --opt build-arg:TESTS=gated --progress=quiet || exit 1
exit 0
