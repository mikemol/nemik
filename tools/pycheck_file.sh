#!/bin/sh
# nemik:W2055: bazel run //:pycheck_file -- PATH [PATH ...]: the lint and type verdict on named files.
# The built //:.venv's own mikemol-pycheck runs on each (as tests/venv_pytest.sh runs pytest), from the
# workspace, so the repository's pyproject.toml and house configuration apply and PATHs are written
# relative to it. Exit 0 means every file is admitted; the last refusal's exit status is returned. It
# runs the console script, not `python -m mikemol.hooks.pycheck_cli`: that module has no __main__ guard,
# so run that way it prints nothing and exits 0 on any file (a false pass, found on this card).
set -eu
venv="${RUNFILES_DIR:-$0.runfiles}/_main/.venv"
[ -x "$venv/bin/mikemol-pycheck" ] || { echo "pycheck_file: $venv/bin/mikemol-pycheck not staged" >&2; exit 1; }
PYTHONHOME="${RUNFILES_DIR:-$0.runfiles}/$(cat "$venv/pythonhome.runfiles")"
export PYTHONHOME
cd "${BUILD_WORKSPACE_DIRECTORY:-.}" || exit 1
status=0
for path in "$@"; do
    "$venv/bin/mikemol-pycheck" --check-file "$path" || status=$?
done
exit "$status"
