#!/bin/sh
# nemik: the render check (nemik:W306): tests/test_layout.py drives the web view in a real browser
# (layout budgets, the rank forest, repo toggles, salience order, a11y cues) and leaves screenshots.
#
#   tools/render-check.sh [extra pytest args]
#
# nemik:W398: by default it runs the gate's OWN target, `bazel test //:test_layout`, so the browser is the
# gate's pinned headless Chrome with its fonts: a pass here is a pass in the gate. (Run on the host's Chrome
# it once passed while the gate failed: a label glyph missing from the gate's fonts drew as a wide box.)
# Screenshots land in bazel-testlogs/test_layout/test.outputs/.
#
#   HOST_CHROME=1 tools/render-check.sh   the old host step, against /usr/bin/google-chrome-stable (or
#                                         $NEMIK_CHROMIUM), screenshots under $SHOTS (/var/tmp/nemik-shots)
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
if [ "${HOST_CHROME:-0}" != 1 ]; then
	cd "$here"
	exec bazel test //:test_layout --test_output=errors
fi
chrome=${NEMIK_CHROMIUM:-/usr/bin/google-chrome-stable}
shots=${SHOTS:-/var/tmp/nemik-shots}
mkdir -p "$shots"
exec env NEMIK_CHROMIUM="$chrome" TEST_UNDECLARED_OUTPUTS_DIR="$shots" \
	"$here/.venv/bin/python3" -m pytest "$here/tests/test_layout.py" -q "$@"
