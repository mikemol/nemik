#!/bin/sh
# nemik:W103: every test runs under the built //:.venv's own interpreter (operator: "bazel builds
# the .venv ... That .venv is then a build input for everything subsequent"), so what is tested is
# what is installed, not a py_test's per-target import path. mtools' mutate_check.sh pattern:
# invoke the venv through its bin/ path (that is what sets sys.prefix), and name the staged
# toolchain with PYTHONHOME, since bazel resolves the interpreter symlink at staging.
set -eu
venv="${RUNFILES_DIR:-$TEST_SRCDIR}/_main/.venv"
[ -x "$venv/bin/python3" ] || { echo "venv_pytest: $venv/bin/python3 not staged" >&2; exit 1; }
PYTHONHOME="${RUNFILES_DIR:-$TEST_SRCDIR}/$(cat "$venv/pythonhome.runfiles")"
export PYTHONHOME
exec "$venv/bin/python3" -m pytest -p no:cacheprovider -q "$@"
