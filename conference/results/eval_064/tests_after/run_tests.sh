#!/usr/bin/env bash
set -euo pipefail
out="$PWD/tests_after"
repo="$(cd ../../.. && pwd)"
py="$HOME/.venvs/thesis-python/bin/python"
date -Is > "$out/started.txt"
git -C "$repo" rev-parse HEAD > "$out/commit.txt"
git -C "$repo" status --short -uno > "$out/tracked_status.txt"
"$py" -VV > "$out/python.txt"
"$py" -m pip freeze > "$out/pip_freeze.txt"
"$py" -m pip check > "$out/pip_check.txt"
checkout=$(mktemp -d /tmp/064-tests-after.XXXXXX)
trap 'rm -rf -- "$checkout"' EXIT
git clone -q --shared --no-checkout --branch claude/064-eval "$repo" "$checkout"
git -C "$checkout" restore --source=HEAD --staged --worktree -- conference/
test "$(git -C "$checkout" rev-parse HEAD)" = "$(cat "$out/commit.txt")"
cd "$checkout/conference"
export PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1
export MPLCONFIGDIR="$checkout/.mpl" XDG_CACHE_HOME="$checkout/.cache"
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
