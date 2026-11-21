#!/usr/bin/env bash
# Hayashi only, after task044. One paired CPU/GPU run with the original sensors.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
out=${1:?Usage: run_smoke.sh NEW_OUTPUT_DIR [VENv_PYTHON]}
py=${2:-$HOME/.venvs/thesis-python/bin/python}
mkdir -- "$out"
out=$(realpath "$out")
image=${THESIS_ROS_IMAGE:-thesis/jazzy-gz:1}
domain=${THESIS_ROS_DOMAIN_ID:-65}
patch=08OB88_-1417
{
  date -Is
  git rev-parse HEAD
  git status --short -uno
  docker image inspect "$image" --format '{{.Id}}'
} > "$out/conditions.txt"
nvidia-smi > "$out/host_nvidia_smi.txt"
if ! docker run --rm --pull=never --gpus all -e NVIDIA_DRIVER_CAPABILITIES=all "$image" nvidia-smi \
      > "$out/container_nvidia_smi.txt" 2>&1; then
  cat "$out/container_nvidia_smi.txt" >&2
  printf '%s\n' 'Docker NVIDIA preflight failed. Check NVIDIA Container Toolkit and Docker GPU configuration.' >&2
  exit 2
fi

monitor= container=
cleanup() {
  if [[ -n "$monitor" ]]; then kill "$monitor" 2>/dev/null || true; fi
  if [[ -n "$container" ]]; then docker stop --time 20 "$container" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

status=0
args=(--map fine --real-time-factor 1.0 --ground-estimate non_obstacle --online-fixes v2
      --sensors lidar_real+depth2 --diagnostics)
printf 'patch=%s domain=%s image=%s\nargs=%s\n' "$patch" "$domain" "$image" "${args[*]}" >> "$out/conditions.txt"
for mode in cpu gpu; do
  trial="$out/$mode"
  mkdir "$trial"
  nvidia-smi --query-gpu=timestamp,index,name,utilization.gpu,utilization.memory \
    --format=csv,noheader,nounits --loop-ms=1000 > "$trial/gpu_usage.csv" 2> "$trial/gpu_usage_error.txt" &
  monitor=$!
  THESIS_RENDER="$mode" THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH="$patch" THESIS_ROS_DOMAIN_ID="$domain" \
    THESIS_SOFTWARE_RENDERING=1 THESIS_STALE_TIMEOUT_S=1.0 THESIS_ROS_IMAGE="$image" \
    bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$trial/physical_1" "${args[@]}" > "$trial/console.txt" 2>&1 &
  runner=$!
  probe=
  while kill -0 "$runner" 2>/dev/null; do
    while read -r id; do
      [[ -n "$id" ]] || continue
      mount=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/output"}}{{.Source}}{{end}}{{end}}' "$id") || continue
      [[ "$mount" == "$trial/physical_1" ]] || continue
      container=$id
      docker exec "$container" bash -c 'source /opt/ros/jazzy/setup.bash &&
        exec python3 /conference/results/gpu_rendering/cloud_pair.py capture /output/clouds' \
        > "$trial/probe.txt" 2>&1 &
      probe=$!
      break 2
    done < <(docker ps -q --filter "ancestor=$image")
    sleep 0.2
  done
  rc=0
  wait "$runner" || rc=$?
  container=
  printf '%s\n' "$rc" > "$trial/exit.txt"
  if (( rc != 0 )); then status=1; fi
  if [[ -n "$probe" ]]; then
    probe_rc=0
    wait "$probe" || probe_rc=$?
    printf '%s\n' "$probe_rc" > "$trial/probe_exit.txt"
  fi
  kill "$monitor" 2>/dev/null || true
  wait "$monitor" || true
  monitor=
done
"$py" results/gpu_rendering/cloud_pair.py compare "$out" | tee "$out/summary.json"
exit "$status"
