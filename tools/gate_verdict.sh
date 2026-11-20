#!/bin/sh
# nemik:W2345: run tools/gate_verdict.py under the built //:.venv's interpreter, as a build tool. The
# same pattern as tests/venv_pytest.sh: invoke the venv through its bin/ path (that sets sys.prefix)
# and name the staged toolchain with PYTHONHOME, since bazel resolves the interpreter symlink at staging.
# The arguments are the script's own (`judge KIND OUT FILE...`); paths are relative to the action's cwd.
set -eu
runfiles="${RUNFILES_DIR:-$0.runfiles}"
venv="$runfiles/_main/.venv"
[ -x "$venv/bin/python3" ] || { echo "gate_verdict: $venv/bin/python3 not staged" >&2; exit 1; }
PYTHONHOME="$runfiles/$(cat "$venv/pythonhome.runfiles")"
export PYTHONHOME
exec "$venv/bin/python3" "$runfiles/_main/tools/gate_verdict.py" "$@"
