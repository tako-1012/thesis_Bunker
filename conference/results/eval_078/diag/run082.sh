#!/usr/bin/env bash
# Exactly two 078-matched runs. Record the second run only.
set -euo pipefail
cd "$(dirname "$0")/../../.."
out="$PWD/results/eval_078/diag"
pin=cc9b42f477555470dcba7adbb44fd0b46aa0a678
py="$PWD/.venv-localization/bin/python"
image_tag=thesis/jazzy-gz:1
test "$(git rev-parse HEAD)" = "$pin"
test "$(git branch --show-current)" = claude/082-frame-check
test -z "$(git status --short --untracked-files=no)"
test "$(cat "$out/../batch_exit.txt")" = 0
test ! -e "$out/confirmations"
test ! -e "$out/compare_exit.txt"
exec 9>"$out/compare.lock"
flock -n 9
trap 'rc=$?; echo "$rc" > "$out/compare_exit.txt"; echo "$(date -Is) BATCH_EXIT $rc"' EXIT
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
unset THESIS_SOFTWARE_RENDERING

patch=08OB88_-1417
image=$(docker image inspect "$image_tag" --format '{{.Id}}')
old_image=$(sed -n 's/.* image=\([^ ]*\).*/\1/p' "$out/../batch_conditions.txt")
test "$image" = "$old_image"
test -r /usr/share/glvnd/egl_vendor.d/10_nvidia.json
mkdir "$out/confirmations"

for mode in off on; do
    active=$(docker ps -q --filter "ancestor=$image_tag")
    if [[ -n "$active" ]] || pgrep -af '[g]z sim|[g]z-sim'; then
        echo "Another Gazebo run is active."
        exit 2
    fi
    run="$out/confirmations/$mode"
    mkdir "$run"
    args=(--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2
          --sensors lidar_real+depth2 --diagnostics --terrain-source prior --obstacle-clearance distance
          --save-plan-maps --pose-trace --real-time-factor 1.0 --landmarks 0 --landmark-seed 0)
    if [[ "$mode" == on ]]; then
        args+=(--record-sensors --record-sensors-seconds 120)
    fi
    {
        echo "started=$(date -Is) commit=$pin branch=claude/082-frame-check"
        echo "image=$image patch=$patch condition=$mode density_per_ha=0 seed=0 domain=78 rtf=1.0 rendering=gpu stale_sim_s=1.0 protocol=rtf_check"
        printf 'args=%s\n' "${args[*]}"
    } > "$run/run_conditions.txt"
    nice -n 19 "$py" -u "$out/process_usage082.py" "$run/process_usage.csv" "$run/monitor.stop" \
        > "$run/monitor_log.txt" 2>&1 &
    sampler=$!
    echo "$(date -Is) START $mode"
    rc=0
    THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH="$patch" THESIS_ROS_DOMAIN_ID=78 \
        THESIS_RENDER=gpu THESIS_STALE_TIMEOUT_S=1.0 THESIS_ROS_IMAGE="$image_tag" \
        bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$run/physical_1" "${args[@]}" \
        > "$run/console_log.txt" 2>&1 || rc=$?
    printf '%s\n' "$rc" > "$run/exit.txt"
    touch "$run/monitor.stop"
    wait "$sampler" || echo "Process monitor failed for $mode; see monitor_log.txt."
    echo "$(date -Is) END $mode exit=$rc"
done
echo "$(date -Is) BATCH_FINISHED 2"
