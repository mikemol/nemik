#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
#
# nemik:W866: solve the Containerfile with the pinned BuildKit frontend, so an image build that cannot
# even be converted (nemik:W865: COPY --from took a variable, "failed to parse stage name", and no
# image shipped for hours) fails the commit and not the forge's build. It builds the `gated` path,
# which is the shared final stage and takes seconds; the `test` path differs only in which stage the
# final one takes its marker from, so a conversion error shows in either.
#   tools/image_solve.sh [DIR]   exit 0 = it solved; 3 = no BuildKit to ask (skipped, say why);
#                                any other exit = the solve failed
set -uo pipefail

dir="$(cd "${1:-.}" && pwd)" || exit 2
if ! command -v buildctl >/dev/null 2>&1; then
	printf 'image_solve: no buildctl on this host\n'
	exit 3
fi
if ! buildctl debug workers >/dev/null 2>&1; then
	printf 'image_solve: no BuildKit daemon answers buildctl\n'
	exit 3
fi
printf 'image_solve: %s\n' "$dir"
buildctl build --frontend dockerfile.v0 \
	--local "context=$dir" --local "dockerfile=$dir" \
	--opt filename=Containerfile --opt build-arg:TESTS=gated --progress=quiet
exit $?
