#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
root="$PWD/results/eval_078/diag084"
py="$PWD/.venv-localization/bin/python"
pin=b0dd82ea2420b56ce48305854422d6a2c96c97f3
test "$(git rev-parse HEAD)" = "$pin"
test "$(git branch --show-current)" = claude/084-self-hit
test -z "$(git status --short --untracked-files=no)"
test ! -e "$root/replay"
test ! -e "$root/replay_exit.txt"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1 TBB_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.
"$py" -m pip freeze > "$root/localization_pip_freeze.txt"
printf '%s\n' "$pin" > "$root/execution_commit.txt"
printf '%s\n' "$(date -Is)" > "$root/started.txt"
trap 'rc=$?; printf "%s\n" "$rc" > "$root/replay_exit.txt"; date -Is' EXIT

(
    cd "$root/.."
    for label in 08OB88_-1417/d160_s0 08OB88_-1417/d0_s0 08OB86_-0205/d40_s1; do
        phys="runs/$label/physical_1"
        find "$phys/raw" -type f \( -name reference_cloud.npz -o -path '*/sensors/*' \) -print0
        printf '%s\0' "$phys/manifest.json"
    done | LC_ALL=C sort -z | xargs -0 sha256sum
) > "$root/input_sha256.txt"
"$py" -u "$root/self_hit084.py" inspect
mkdir "$root/replay_logs"
for trial in 1417_d160_s0 1417_d0_s0 0205_d40_s1; do
    printf '%s raw\n%s filtered\n' "$trial" "$trial"
done | xargs -n 2 -P 2 bash -c '
    root=$1; python=$2; trial=$3; mode=$4; status=0
    echo "$(date -Is) START $trial $mode"
    "$python" -u "$root/self_hit084.py" "$trial" "$mode" > "$root/replay_logs/${trial}_${mode}.txt" 2>&1 || status=$?
    echo "$(date -Is) END $trial $mode $status"
    exit "$status"
' _ "$root" "$py"
(
    cd "$root/.."
    sha256sum -c --quiet "$root/input_sha256.txt"
)
test "$(find "$root/replay" -name summary.csv | wc -l)" -eq 6
date -Is > "$root/finished.txt"
echo "Six replays completed and original sensor files still match SHA-256"
