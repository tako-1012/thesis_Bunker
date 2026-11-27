#!/usr/bin/env bash
# Task 073: one preflight test suite, then eight pose-error conditions per beach and repetition.
set -euo pipefail
cd "$(dirname "$0")/../.."
root="$PWD/results/eval_073"
py="$HOME/.venvs/thesis-python/bin/python"
branch=claude/073-eval
commit=$(git rev-parse HEAD)
domain=73
image_tag=thesis/jazzy-gz:1
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
unset THESIS_SOFTWARE_RENDERING
test "$commit" = "$1"
test_checkout=$2
test "$(git -C "$test_checkout" rev-parse HEAD)" = "$commit"
test -z "$(git -C "$test_checkout" status --porcelain)"
test "$(git branch --show-current)" = "$branch"
test -z "$(git status --short --untracked-files=no)"
test ! -e "$root/tests"
test ! -e "$root/runs"
test ! -e "$root/batch_exit.txt"
exec 9>"$root/run.lock"
flock -n 9
trap 'rc=$?; printf "%s\n" "$rc" > "$root/batch_exit.txt"; echo "$(date -Is) BATCH_EXIT $rc"' EXIT

ensure_idle() {
    local other_containers
    other_containers=$(docker ps -q --filter "ancestor=$image_tag")
    if [[ -n "$other_containers" ]] || pgrep -af '[g]z sim|[g]z-sim'; then
        echo "Another Gazebo run is active."
        exit 2
    fi
}

ensure_idle
mkdir "$root/tests"
printf '%s\n' "$commit" > "$root/tests/commit.txt"
printf '%s\n' "$test_checkout" > "$root/tests/checkout.txt"
git status --short --untracked-files=no > "$root/tracked_status_before.txt"
"$py" -m pip freeze | awk '!/ @ / && !/^[-]e /' > "$root/tests/pip_freeze.txt"
nvidia-smi > "$root/gpu.txt"
df -h "$root" > "$root/disk_before.txt"
date -Is > "$root/tests/started.txt"
git -C "$test_checkout/conference" ls-files 'tests/test_*.py' > "$root/tests/files.txt"
test -s "$root/tests/files.txt"
"$py" - "$test_checkout/conference" "$root/tests" <<'PYTEST'
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import subprocess
import sys

conference, destination = map(Path, sys.argv[1:])
modules = [path.removesuffix(".py").replace("/", ".")
           for path in (destination / "files.txt").read_text().splitlines()]


def run_test(module):
    with (destination / f"{module}.txt").open("x") as log:
        process = subprocess.run([sys.executable, "-u", "-m", module], cwd=conference,
                                 stdout=log, stderr=subprocess.STDOUT)
    return module, process.returncode


with ThreadPoolExecutor(max_workers=4) as pool, (destination / "summary.txt").open("x") as summary:
    for finished in as_completed([pool.submit(run_test, module) for module in modules]):
        module, code = finished.result()
        summary.write(f"{module} {code}\n")
        summary.flush()
        print(f"{datetime.now().astimezone().isoformat(timespec='seconds')} TEST {module} {code}", flush=True)
PYTEST
date -Is > "$root/tests/finished.txt"
count=$(wc -l < "$root/tests/summary.txt")
if ! awk 'NF!=2 || $2!=0 {print; bad++} END {exit (bad>0)}' "$root/tests/summary.txt"; then
    echo "$(date -Is) TESTS_FAILED $count; see tests/summary.txt and individual logs."
    exit 1
fi
test "$(git rev-parse HEAD)" = "$commit"
test -z "$(git status --short --untracked-files=no)"
test "$(git -C "$test_checkout" rev-parse HEAD)" = "$commit"
test -z "$(git -C "$test_checkout" status --short --untracked-files=no)"
echo "$(date -Is) TESTS_PASSED $count commit=$commit"

ensure_idle
test -r /usr/share/glvnd/egl_vendor.d/10_nvidia.json
image=$(docker image inspect "$image_tag" --format '{{.Id}}')
docker run --rm --pull=never --gpus all -e NVIDIA_DRIVER_CAPABILITIES=all "$image_tag" \
    bash -lc 'set -e; nvidia-smi; source /opt/ros/jazzy/setup.bash; gz sim --versions' \
    > "$root/container_gpu_gazebo.txt" 2>&1

patches=(08OB86_-0205 08OB88_-1417 08OB88_00332 08OB89_-0847)
# The none mode keeps the original trace schema. Start each round with bias025 to verify paired poses.
conditions=(bias025 none bias050 bias100 yaw2 drift05 drift1 drift2)
{
    echo "commit=$commit branch=$branch image=$image domain=$domain"
    echo "patches=${patches[*]}"
    echo "condition_order=${conditions[*]}"
    echo "repetitions=1 2 3 4 5"
} > "$root/batch_conditions.txt"
date -Is > "$root/started.txt"

for patch in "${patches[@]}"; do
    for rep in 1 2 3 4 5; do
        for condition in "${conditions[@]}"; do
            ensure_idle
            test "$(git rev-parse HEAD)" = "$commit"
            run="$root/runs/$patch/${condition}_r$rep"
            mkdir -p "$(dirname "$run")"
            mkdir "$run"
            case "$condition" in
                none)    error_args=(--pose-error none) ;;
                bias025) error_args=(--pose-error bias --pose-error-bias=.25,0,0) ;;
                bias050) error_args=(--pose-error bias --pose-error-bias=.5,0,0) ;;
                bias100) error_args=(--pose-error bias --pose-error-bias=1,0,0) ;;
                yaw2)    error_args=(--pose-error bias --pose-error-bias=0,0,2) ;;
                drift05) error_args=(--pose-error drift --pose-error-drift-pct .5) ;;
                drift1)  error_args=(--pose-error drift --pose-error-drift-pct 1) ;;
                drift2)  error_args=(--pose-error drift --pose-error-drift-pct 2) ;;
            esac
            args=(--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2
                  --sensors lidar_real+depth2 --diagnostics --terrain-source prior --obstacle-clearance distance
                  --save-plan-maps --pose-trace --real-time-factor 1.0
                  --pose-error-seed 0 --pose-error-rep "$rep" "${error_args[@]}")
            {
                echo "started=$(date -Is) commit=$commit branch=$branch tracked_changes=0"
                echo "image=$image patch=$patch condition=$condition rep=$rep rtf=1.0 domain=$domain rendering=gpu stale_sim_s=1.0 seed=0 protocol=rtf_check"
                printf 'args=%s\n' "${args[*]}"
            } > "$run/run_conditions.txt"
            echo "$(date -Is) START $patch $condition $rep"
            code=0
            THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH="$patch" THESIS_ROS_DOMAIN_ID="$domain" \
                THESIS_RENDER=gpu THESIS_STALE_TIMEOUT_S=1.0 THESIS_ROS_IMAGE="$image_tag" \
                bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$run/physical_1" "${args[@]}" \
                > "$run/console_log.txt" 2>&1 || code=$?
            printf '%s\n' "$code" > "$run/exit.txt"
            echo "$(date -Is) END $patch $condition $rep exit=$code bytes=$(du -sb "$run" | cut -f1)"
            if ((code != 0)); then
                echo "Stopped after process exit $code. See $run/console_log.txt."
                exit "$code"
            fi
            if [[ "$patch" == "${patches[0]}" && "$rep" == 1 && "$condition" == "${conditions[0]}" ]]; then
                if ! "$py" - "$run" "$patch" <<'PYFIRST' | tee "$root/first_check.json"; then
import csv
import json
import math
from pathlib import Path
import sys

trial, patch = Path(sys.argv[1]), sys.argv[2]
physical = trial / "physical_1"
result = {"patch": patch, "condition": "bias025", "rep": 1, "rtf_min": 0.9, "errors": []}
errors = result["errors"]


def bytes_under(folder):
    return sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())


try:
    manifest = json.loads((physical / "manifest.json").read_text())
    case, = [case for case in manifest["cases"] if case["selected"]]
    raw = physical / case["run_folder"]
    result.update(execution=manifest.get("execution"), termination=case.get("termination"))
    if case["patch"] != patch or result["execution"] != "finished":
        errors.append("The expected beach did not have a finished execution.")
    if manifest["rendering"]["mode"] != "gpu" or manifest["real_time_factor"] != 1.0:
        errors.append("The manifest does not describe the requested render and time settings.")
    render = case["rendering"]
    result.update({key: render.get(key) for key in ("gpu_rendered", "gl_vendor", "gl_renderer")})
    if result["gpu_rendered"] is not True or "nvidia" not in str(result["gl_vendor"]).lower():
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
    pair_file = trace / "pose_error.csv"
    result.update(plan_map_bytes=bytes_under(maps), pose_trace_bytes=bytes_under(trace),
                  trial_bytes=bytes_under(trial), plan_map_count=len(list(maps.glob("plan_*.npz"))),
                  plan_map_limit_bytes=int(manifest["plan_map_limit_bytes"]),
                  pose_trace_limit_bytes=int(manifest["pose_trace_limit_bytes"]),
                  plan_maps_incomplete=(maps / "incomplete.json").exists())
    if (not manifest.get("save_plan_maps") or not result["plan_map_count"] or result["plan_maps_incomplete"]
            or result["plan_map_bytes"] > result["plan_map_limit_bytes"]):
        errors.append("The plan maps were missing, incomplete, or above their limit.")
    if not manifest.get("pose_trace") or result["pose_trace_bytes"] > result["pose_trace_limit_bytes"]:
        errors.append("The pose trace was disabled or above its limit.")
    if manifest.get("pose_error") != "bias":
        errors.append("The manifest did not record the bias condition.")

    axes = ("x", "y", "z", "roll", "pitch", "yaw")
    fields = [f"{kind}_{axis}" for kind in ("truth", "estimated") for axis in axes]
    offsets = []
    with pair_file.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(fields).issubset(reader.fieldnames or []):
            raise ValueError("pose_error.csv is missing truth or estimated pose columns.")
        for row in reader:
            values = [float(row[field]) for field in fields]
            if not all(map(math.isfinite, values)):
                raise ValueError("pose_error.csv contains non-finite pose values.")
            offsets.append(math.hypot(values[6] - values[0], values[7] - values[1]))
    result.update(pose_error_path=str(pair_file.relative_to(trial)), pose_error_bytes=pair_file.stat().st_size,
                  pose_error_samples=len(offsets), paired_pose_fields=fields)
    if not offsets:
        errors.append("pose_error.csv has no paired poses.")
    else:
        result.update(pose_error_min_m=min(offsets), pose_error_max_m=max(offsets))
        if not all(math.isclose(offset, 0.25, rel_tol=0, abs_tol=1e-6) for offset in offsets):
            errors.append("Paired poses do not show the specified 0.25 m horizontal bias.")
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

date -Is > "$root/finished.txt"
echo "$(date -Is) BATCH_FINISHED 160"
