#!/bin/sh
# nemik: format a .py draft, then lint and type-check it, so a multi-region change lands clean in one
# step instead of through the edit gate's one-region-at-a-time refusals (pycheck refuses an unformatted
# or half-imported file; its fixes are all mechanical).
#
#   tools/pyfmt.sh <draft> <dest.py>
#
# <draft> is any text file (keep it out of src/ and name it so pycheck does not read it, e.g. .txt). It
# is formatted with the venv's ruff, written to <dest.py>, and then ruff check and mypy run on it. Exit
# non-zero if either finds anything; the file is left in place so the findings can be read in context.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
python="$here/.venv/bin/python3"
draft=$1
dest=$2
"$python" -m ruff format --stdin-filename "$dest" <"$draft" >"$dest.new"
mv "$dest.new" "$dest"
"$python" -m ruff check "$dest"
"$python" -m mypy "$dest"
