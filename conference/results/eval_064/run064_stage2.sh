#!/usr/bin/env bash
# Task 064 stage 2: three S/P/D/PD/G/GD rounds per beach, one run at a time.
set -euo pipefail
cd "$(dirname "$0")/../.."
root="$PWD/results/eval_064"
stage="$root/stage2"
runtime="$(cat "$stage/runtime_path.txt")"
cd "$runtime/conference"
py="$HOME/.venvs/thesis-python/bin/python"
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
unset THESIS_SOFTWARE_RENDERING
test -d "$root/runs"
test -s "$root/finished.txt"
test "$(cat "$root/batch_exit.txt")" = 0
test ! -e "$stage/batch_exit.txt"
test -z "$(find "$root/runs" -mindepth 2 -maxdepth 2 -type d \( -name "*_r4" -o -name "*_r5" -o -name "*_r6" \) -print -quit)"
exec 9>"$stage/run.lock"
flock -n 9
trap 'rc=$?; printf "%s\n" "$rc" > "$stage/batch_exit.txt"; echo "$(date -Is) BATCH_EXIT $rc"' EXIT

while tmux has-session -t =tests064-stage2 2>/dev/null; do sleep 3; done
if [[ ! -s "$stage/tests/finished.txt" || ! -s "$stage/tests/summary.txt" ]]; then
    echo "Preflight failed before the test suite finished; see tests/session_log.txt."
    exit 1
fi
expected=$(git ls-files 'tests/test_*.py' | sed -E 's#tests/(.*)\.py#tests.\1#' | LC_ALL=C sort)
observed=$(awk 'NF==2 && $2==0 {print $1}' "$stage/tests/summary.txt" | LC_ALL=C sort)
if [[ "$expected" != "$observed" ]] || ! awk 'NF!=2 || $2!=0 {print; bad++} END {exit (bad>0)}' "$stage/tests/summary.txt"; then
    echo "Preflight failed; see tests/summary.txt and the individual logs."
    exit 1
fi
commit=$(git rev-parse HEAD)
test "$commit" = "$(cat "$stage/tests/commit.txt")"
test "$commit" = 7f946a3c5a01e1a73de9c33986fab21fe0fe7785
git diff --exit-code HEAD -- .
count=$(wc -l < "$stage/tests/summary.txt")
echo "$(date -Is) TESTS_PASSED $count commit=$commit"

image_tag=thesis/jazzy-gz:1
image=$(docker image inspect "$image_tag" --format '{{.Id}}')
if ! grep -Fq "image=$image stage=1 " "$root/runs/08OB86_-0205/S_r1/run_conditions.txt"; then
    echo "The Docker image differs from stage 1; stopped before launching."
    exit 2
fi
domain=68

ensure_idle() {
    if [[ -n "$(docker ps -q --filter "ancestor=$image_tag")" ]] || pgrep -af '[g]z sim|[g]z-sim'; then
        echo "Another Gazebo run is active; stopped before launching a trial."
        exit 2
    fi
}

ensure_idle
test -r /usr/share/glvnd/egl_vendor.d/10_nvidia.json
nvidia-smi > "$stage/gpu.txt"
if ! docker run --rm --pull=never --gpus all -e NVIDIA_DRIVER_CAPABILITIES=all "$image_tag" \
    nvidia-smi > "$stage/container_nvidia_smi.txt" 2>&1; then
    cat "$stage/container_nvidia_smi.txt"
    echo "Container GPU preflight failed."
    exit 2
fi
df -h "$root" > "$stage/disk_before.txt"

for patch in 08OB86_-0205 08OB88_-1417 08OB88_-0167 08OB88_00332 08OB89_-0847; do
    for rep in 4 5 6; do
        for condition in S P D PD G GD; do
            ensure_idle
            run="$root/runs/$patch/${condition}_r$rep"
            test ! -e "$run"
            args=(--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2
                  --sensors lidar_real+depth2 --diagnostics --real-time-factor 1.0 --save-plan-maps --pose-trace)
            case "$condition" in
                P)  args+=(--terrain-source prior) ;;
                D)  args+=(--obstacle-clearance distance) ;;
                PD) args+=(--terrain-source prior --obstacle-clearance distance) ;;
                G)  args+=(--ground-near-obstacle exclude) ;;
                GD) args+=(--ground-near-obstacle exclude --obstacle-clearance distance) ;;
            esac
            previous="$root/runs/$patch/${condition}_r$((rep-3))"
            if [[ "$(sed -n 's/^args=//p' "$previous/run_conditions.txt")" != "${args[*]}" ]]; then
                echo "The trial options differ from $previous; stopped before launching."
                exit 2
            fi
            mkdir -- "$run"
            {
                echo "started=$(date -Is) commit=$commit branch=claude/064-eval tracked_changes=0"
                echo "image=$image stage=2 patch=$patch condition=$condition rep=$rep rtf=1.0 domain=$domain rendering=gpu stale_sim_s=1.0 seed=0 prior_variant=exact"
                printf 'args=%s\n' "${args[*]}"
            } > "$run/run_conditions.txt"
            echo "$(date -Is) START $patch $condition $rep"
            rc=0
            THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH="$patch" THESIS_ROS_DOMAIN_ID="$domain" \
                THESIS_RENDER=gpu THESIS_STALE_TIMEOUT_S=1.0 THESIS_ROS_IMAGE="$image_tag" \
                bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$run/physical_1" "${args[@]}" \
                > "$run/console_log.txt" 2>&1 || rc=$?
            printf '%s\n' "$rc" > "$run/exit.txt"
            echo "$(date -Is) END $patch $condition $rep exit=$rc bytes=$(du -sb "$run" | cut -f1)"
            if ((rc != 0)); then
                echo "Stopped after process exit $rc; see $run/console_log.txt."
                exit "$rc"
            fi
            if [[ "$patch" == 08OB86_-0205 && "$rep" == 4 && "$condition" == S ]]; then
                if ! "$py" - "$run" "$patch" <<'PYFIRST' | tee "$stage/first_check.json"; then
import csv
import json
import math
from pathlib import Path
import sys

trial, patch = Path(sys.argv[1]), sys.argv[2]
physical = trial / "physical_1"
result = {"patch": patch, "condition": "S", "rep": 4, "rtf_min": 0.9, "errors": []}
errors = result["errors"]


def bytes_under(folder):
    return sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())


try:
    manifest = json.loads((physical / "manifest.json").read_text())
    case, = [case for case in manifest["cases"] if case["selected"]]
    raw = physical / case["run_folder"]
    result.update(execution=manifest.get("execution"), termination=case.get("termination"))
    if case["patch"] != patch or manifest.get("execution") != "finished":
        errors.append("The expected beach did not have a finished execution.")
    if manifest.get("rendering", {}).get("mode") != "gpu" or manifest.get("real_time_factor") != 1.0:
        errors.append("The manifest does not describe the requested run settings.")
    render = case.get("rendering", {})
    result.update({key: render.get(key) for key in ("gpu_rendered", "gl_vendor", "gl_renderer")})
    if result["gpu_rendered"] is not True:
        errors.append("NVIDIA rendering was not confirmed in the manifest.")

    mission = json.loads((raw / "mission.json").read_text())
    sim = float(mission["finished_t"]) - float(mission["started_t"])
    wall = float(mission["wall_elapsed_s"])
    if not all(math.isfinite(value) and value > 0 for value in (sim, wall)):
        errors.append("Mission timing cannot be used to measure RTF.")
    else:
        result.update(sim_s=sim, wall_s=wall, measured_rtf=sim / wall)
        if result["measured_rtf"] < result["rtf_min"]:
            errors.append("The measured RTF was below 0.9.")

    maps, trace = raw / "plan_maps", raw / "pose_trace"
    result.update(plan_map_bytes=bytes_under(maps), pose_trace_bytes=bytes_under(trace),
                  trial_bytes=bytes_under(trial), plan_map_count=len(list(maps.glob("plan_*.npz"))),
                  plan_map_limit_bytes=int(manifest["plan_map_limit_bytes"]),
                  pose_trace_limit_bytes=int(manifest["pose_trace_limit_bytes"]),
                  plan_maps_incomplete=(maps / "incomplete.json").exists(),
                  previous_pose_trace_segments=sorted(path.name for path in trace.glob("*_previous.csv")))
    if (not manifest.get("save_plan_maps") or not result["plan_map_count"] or result["plan_maps_incomplete"]
            or result["plan_map_bytes"] > result["plan_map_limit_bytes"]):
        errors.append("The recorded plan maps were missing, incomplete, or above their limit.")
    if not manifest.get("pose_trace") or result["pose_trace_bytes"] > result["pose_trace_limit_bytes"]:
        errors.append("The recorded pose trace was disabled or above its limit.")
    result["pose_trace_streams"] = {}
    for name in ("follower_pose.csv", "planner_pose.csv", "observer_pose.csv", "follower_tick.csv", "cpu.csv"):
        path = trace / name
        if path.is_file():
            with path.open(newline="") as stream:
                reader = csv.reader(stream)
                next(reader, None)
                samples = sum(1 for row in reader if row)
            result["pose_trace_streams"][name] = {"samples": samples, "bytes": path.stat().st_size}
        else:
            samples = 0
        if not samples:
            errors.append(f"No samples in pose trace stream {name}.")
    for log in [trial / "console_log.txt", *sorted(raw.glob("process_*.txt"))]:
        text = log.read_text(errors="replace")
        if "pose trace disabled for" in text or "pose trace close failed for" in text:
            errors.append(f"Pose trace write error in {log.name}.")
except (OSError, KeyError, TypeError, ValueError) as error:
    errors.append(str(error))

result["passed"] = not errors
print(json.dumps(result, indent=2, allow_nan=False))
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

date -Is > "$stage/finished.txt"
echo "$(date -Is) STAGE_2_FINISHED 90"
