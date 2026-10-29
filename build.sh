#!/usr/bin/env bash
# Build through the project environment from any working directory.
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd -- "$project_root"

if [[ ! -x .venv/bin/python ]]; then
    printf '%s\n' 'The .venv environment was not found. Set it up as described in README.md.' >&2
    exit 1
fi

export TMPDIR="$project_root/build/tmp"
export TEMP="$TMPDIR"
export TMP="$TMPDIR"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p -- "$TMPDIR"

build_output="build/standalone-$(date +%Y%m%d-%H%M%S)-$$"
exec .venv/bin/python -B scripts/build_desktop.py \
    --output "$build_output" --jobs 2 "$@"
