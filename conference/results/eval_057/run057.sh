#!/usr/bin/env bash
# Task 057: run S/PG/SGN in fixed order and aggregate the retained records.
set -euo pipefail
cd "$(dirname "$0")/../.."
root="$PWD/results/eval_057"
py="$HOME/.venvs/thesis-python/bin/python"
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
trap 'rc=$?; printf "%s\n" "$rc" > "$root/batch_exit.txt"; echo "$(date -Is) BATCH_EXIT $rc"' EXIT

while tmux has-session -t =tests057 2>/dev/null; do sleep 3; done
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
test "$(git branch --show-current)" = claude/057-eval
test -z "$(git status --short -uno)"
test ! -e "$root/runs"
test ! -e "$root/common_eval"
exec 9>"$root/run.lock"
flock -n 9
image=$(docker image inspect thesis/jazzy-gz:1 --format '{{.Id}}')
nvidia-smi > "$root/gpu.txt"
domain=67
echo "$(date -Is) TESTS_PASSED $count commit=$commit"

for patch in 08OB86_-0205 08OB88_-1417 08OB88_-0167 08OB88_00332 08OB89_-0847; do
    for rep in 1 2 3; do
        for condition in S PG SGN; do
            test -z "$(docker ps -q)"
            if pgrep -af '[g]z sim|[g]z-sim' || pgrep -x ruby; then
                echo "Gazebo or Ruby process already running; stopped before launching this trial."
                exit 2
            fi
            run="$root/runs/$patch/${condition}_r$rep"
            test ! -e "$run"
            mkdir -p "$run"
            args=(--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2
                  --sensors lidar_real+depth2 --diagnostics --real-time-factor 0.3 --save-plan-maps)
            case "$condition" in
                PG) args+=(--terrain-source prior --obstacle-clearance overlap_goal) ;;
                SGN) args+=(--obstacle-clearance overlap_goal --steep-near-obstacle no_inflate) ;;
            esac
            {
                echo "started=$(date -Is) commit=$commit branch=claude/057-eval tracked_changes=0"
                echo "image=$image patch=$patch condition=$condition rep=$rep rtf=0.3 domain=$domain rendering=software stale_sim_s=1.0 seed=0 prior_variant=exact"
                printf 'args=%s\n' "${args[*]}"
            } > "$run/run_conditions.txt"
            echo "$(date -Is) START $patch $condition $rep"
            rc=0
            THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH="$patch" THESIS_ROS_DOMAIN_ID="$domain" \
                THESIS_RENDER=cpu THESIS_SOFTWARE_RENDERING=1 THESIS_STALE_TIMEOUT_S=1.0 THESIS_ROS_IMAGE=thesis/jazzy-gz:1 \
                bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$run/physical_1" "${args[@]}" \
                > "$run/console_log.txt" 2>&1 || rc=$?
            echo "$rc" > "$run/exit.txt"
            echo "$(date -Is) END $patch $condition $rep exit=$rc bytes=$(du -sb "$run" | cut -f1)"
            if ((rc != 0)); then
                echo "Stopped after process exit $rc; see $run/console_log.txt."
                exit "$rc"
            fi

            if [[ "$patch" == 08OB86_-0205 && "$rep" == 1 && "$condition" == S ]]; then
                if ! "$py" - "$run" "$patch" <<'PYFIRST' | tee "$root/first_check.json"; then
import csv
import json
from pathlib import Path
from statistics import median
import sys

from experiments.eval_runs import read_csv, update_metrics


trial = Path(sys.argv[1])
patch = sys.argv[2]
raw = trial / "physical_1" / "raw" / patch
maps = raw / "plan_maps"
max_bytes = 100_000_000
factor = 1.5
keys = ("map_update_s_median", "map_update_s_p95")
result = {"patch": patch, "condition": "S", "rep": 1,
          "plan_map_limit_bytes": max_bytes, "timing_factor": factor, "errors": []}
errors = result["errors"]

try:
    files = [p for p in maps.rglob("*") if p.is_file()]
    result["plan_map_bytes"] = sum(p.stat().st_size for p in files)
    result["plan_map_count"] = len(list(maps.glob("plan_*.npz")))
    result["trial_bytes"] = sum(p.stat().st_size for p in trial.rglob("*") if p.is_file())
    result["incomplete"] = (maps / "incomplete.json").exists()
    if not result["plan_map_count"] or result["incomplete"]:
        errors.append("Plan maps are absent or incomplete.")
    if result["plan_map_bytes"] > max_bytes:
        errors.append("Plan maps exceeded 100,000,000 bytes.")

    baseline_path = Path("results/eval_050/common_eval/runs.csv")
    with baseline_path.open() as stream:
        baseline = sorted(
            (row for row in csv.DictReader(stream)
             if row["patch"] == patch and row["condition"] == "S"),
            key=lambda row: row["rep"],
        )
    if [row["rep"] for row in baseline] != ["1", "2", "3"]:
        raise ValueError("Expected exactly three Task 050 S trials for the first patch.")

    header, rows = read_csv(raw / "map_updates.csv")
    if not header or not rows:
        raise ValueError("Missing map update data.")
    updates = update_metrics(header, rows, None, None)
    result["successful_map_updates"] = updates.get("map_updates", 0)
    result["timing"] = {}
    for key in keys:
        values = [float(row[key]) for row in baseline]
        reference = median(values)
        actual = updates[key]
        if reference <= 0 or actual <= 0:
            raise ValueError(f"Invalid timing for {key}.")
        ratio = actual / reference
        result["timing"][key] = {"actual_s": actual, "baseline_trials_s": values,
                                 "baseline_median_s": reference, "ratio": ratio}
        if not 1 / factor <= ratio <= factor:
            errors.append(f"{key} is outside the accepted range.")
except (OSError, KeyError, ValueError) as error:
    errors.append(str(error))

result["passed"] = not errors
print(json.dumps(result, indent=2))
sys.exit(not result["passed"])
PYFIRST
                    echo "$(date -Is) FIRST_CHECK_FAILED; see first_check.json."
                    exit 3
                fi
                echo "$(date -Is) FIRST_CHECK_PASSED"
            fi
        done
    done
done

"$py" -m experiments.eval_runs "$root/runs" --experiment 057 --out "$root/common_eval" \
    | tee "$root/common_eval_log.txt"
"$py" -m experiments.plan_map_inspect "$root/runs" --out "$root/plan_map_inspect" \
    | tee "$root/plan_map_inspect_log.txt"
date -Is > "$root/finished.txt"
