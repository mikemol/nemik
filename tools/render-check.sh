#!/bin/sh
# nemik: the render check, as a host step (nemik:W306; luthen-observability:W819 advised keeping the
# Bazel gate hermetic, so the browser is not an input to it). Runs tests/test_layout.py, which drives the
# web view in a real browser (layout budgets, the rank forest, repo toggles, salience order), against the
# host's Google Chrome, and leaves the screenshots under $SHOTS (default /var/tmp/nemik-shots).
#
#   tools/render-check.sh [extra pytest args]
#
# Without NEMIK_CHROMIUM the same tests skip inside the gate. Chrome runs with its sandbox on and the
# tests give it a private profile, so the operator's profile is never touched.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
chrome=${NEMIK_CHROMIUM:-/usr/bin/google-chrome-stable}
shots=${SHOTS:-/var/tmp/nemik-shots}
mkdir -p "$shots"
exec env NEMIK_CHROMIUM="$chrome" TEST_UNDECLARED_OUTPUTS_DIR="$shots" \
	"$here/.venv/bin/python3" -m pytest "$here/tests/test_layout.py" -q "$@"
