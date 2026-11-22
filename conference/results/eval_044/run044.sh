#!/usr/bin/env bash
# Task 044: run B/O/T/OT in fixed order and aggregate the retained records.
set -euo pipefail
cd "$(dirname "$0")/../.."
root="$PWD/results/eval_044"
py="$HOME/.venvs/thesis-python/bin/python"
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
trap 'rc=$?; printf "%s\n" "$rc" > "$root/batch_exit.txt"; echo "$(date -Is) BATCH_EXIT $rc"' EXIT

while tmux has-session -t =tests044 2>/dev/null; do sleep 3; done
if [[ ! -s "$root/tests/finished.txt" ]]; then
    echo "Preflight failed before the test suite finished."
    exit 1
fi
count=$(find tests -maxdepth 1 -name 'test_*.py' | wc -l)
if ! awk -v n="$count" '$2 != 0 {print; bad++} END {exit !(NR == n && !bad)}' "$root/tests/summary.txt"; then
    echo "Preflight failed; see tests/summary.txt and the individual logs."
    exit 1
fi
commit=$(git rev-parse HEAD)
test "$commit" = "$(cat "$root/tests/commit.txt")"
test "$(git branch --show-current)" = claude/044-eval
test -z "$(git status --short -uno)"
test ! -e "$root/runs"
test ! -e "$root/common_eval"
exec 9>"$root/run.lock"
flock -n 9
image=$(docker image inspect thesis/jazzy-gz:1 --format '{{.Id}}')
nvidia-smi > "$root/gpu.txt"
domain=65
echo "$(date -Is) TESTS_PASSED $count commit=$commit"

for patch in 08OB86_-0205 08OB88_-1417 08OB88_-0167 08OB88_00332 08OB89_-0847; do
    for rep in 1 2 3; do
        for condition in B O T OT; do
            test -z "$(docker ps -q)"
            if pgrep -af '[g]z sim|[g]z-sim' || pgrep -x ruby; then
                echo "Gazebo or Ruby process already running; stopped before launching this trial."
                exit 2
            fi
            run="$root/runs/$patch/${condition}_r$rep"
            test ! -e "$run"
            mkdir -p "$run"
            args=(--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2
                  --sensors lidar_real+depth2 --diagnostics --real-time-factor 0.3)
            case "$condition" in
                O) args+=(--obstacle-clearance overlap) ;;
                T) args+=(--tracking corner_slow) ;;
                OT) args+=(--obstacle-clearance overlap --tracking corner_slow) ;;
            esac
            {
                echo "started=$(date -Is) commit=$commit branch=claude/044-eval tracked_changes=0"
                echo "image=$image patch=$patch condition=$condition rep=$rep rtf=0.3 domain=$domain rendering=software stale_sim_s=1.0 seed=0"
                printf 'args=%s\n' "${args[*]}"
            } > "$run/run_conditions.txt"
            echo "$(date -Is) START $patch $condition $rep"
            rc=0
            THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH="$patch" THESIS_ROS_DOMAIN_ID="$domain" \
                THESIS_SOFTWARE_RENDERING=1 THESIS_STALE_TIMEOUT_S=1.0 THESIS_ROS_IMAGE=thesis/jazzy-gz:1 \
                bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$run/physical_1" "${args[@]}" \
                > "$run/console_log.txt" 2>&1 || rc=$?
            echo "$rc" > "$run/exit.txt"
            echo "$(date -Is) END $patch $condition $rep exit=$rc bytes=$(du -sb "$run" | cut -f1)"
            if ((rc != 0)); then
                echo "Stopped after process exit $rc; see $run/console_log.txt."
                exit "$rc"
            fi
        done
    done
done

"$py" -m experiments.eval_runs "$root/runs" --experiment 044 --out "$root/common_eval" \
    | tee "$root/common_eval_log.txt"
date -Is > "$root/finished.txt"
