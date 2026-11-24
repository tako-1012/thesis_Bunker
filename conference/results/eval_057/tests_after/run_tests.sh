#!/usr/bin/env bash
set -euo pipefail
out="$PWD/tests_after"
repo="$(cd ../../.. && pwd)"
py="$HOME/.venvs/thesis-python/bin/python"
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
git -C "$repo" rev-parse HEAD > "$out/commit.txt"
date -Is > "$out/started.txt"
"$py" -VV > "$out/python.txt"
"$py" -m pip check > "$out/pip_check.txt"
checkout=$(mktemp -d /tmp/057-tests-after.XXXXXX)
trap 'rm -rf -- "$checkout"' EXIT
git clone -q --shared --no-checkout --branch claude/057-eval "$repo" "$checkout"
git -C "$checkout" restore --source=HEAD --staged --worktree -- conference/
test "$(git -C "$checkout" rev-parse HEAD)" = "$(cat "$out/commit.txt")"
cd "$checkout/conference"
run_test() {
    local file="$1" mod rc=0
    mod="tests.$(basename "$file" .py)"
    "$py" -m "$mod" > "$out/$mod.log" 2>&1 || rc=$?
    printf '%s %s\n' "$mod" "$rc" | tee -a "$out/summary.txt"
}
pids=()
for file in tests/test_*.py; do
    run_test "$file" &
    pids+=("$!")
    if ((${#pids[@]} == 3)); then
        wait "${pids[@]}"
        pids=()
    fi
done
if ((${#pids[@]})); then wait "${pids[@]}"; fi
date -Is > "$out/finished.txt"
