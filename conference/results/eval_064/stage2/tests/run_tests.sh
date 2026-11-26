#!/usr/bin/env bash
set -euo pipefail
out="$PWD/tests"
runtime="$(cat "$PWD/runtime_path.txt")"
py="$HOME/.venvs/thesis-python/bin/python"
date -Is > "$out/started.txt"
git -C "$runtime" rev-parse HEAD > "$out/commit.txt"
test "$(cat "$out/commit.txt")" = 7f946a3c5a01e1a73de9c33986fab21fe0fe7785
git -C "$runtime" status --short -uno -- conference > "$out/tracked_status.txt"
test ! -s "$out/tracked_status.txt"
"$py" -VV > "$out/python.txt"
"$py" -m pip freeze > "$out/pip_freeze.txt"
"$py" -m pip check > "$out/pip_check.txt"
cd "$runtime/conference"
export PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1
export MPLCONFIGDIR="$runtime/.mpl" XDG_CACHE_HOME="$runtime/.cache"
export TEST064_PY="$py" TEST064_OUT="$out"
printf '%s\0' tests/test_*.py | xargs -0 -n 1 -P 4 bash -c '
    module=tests.$(basename "$1" .py)
    rc=0
    {
        printf "\$ %s -m %s\n" "$TEST064_PY" "$module"
        "$TEST064_PY" -m "$module" || rc=$?
    } > "$TEST064_OUT/$module.txt" 2>&1
    printf "%s %s\n" "$module" "$rc" | tee -a "$TEST064_OUT/summary.txt"
' bash
date -Is > "$out/finished.txt"
awk '$2 != 0 {failed=1} END {exit failed}' "$out/summary.txt"
